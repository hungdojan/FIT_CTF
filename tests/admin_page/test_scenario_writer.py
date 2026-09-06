"""ScenarioWriter save/load/collision tests over a tmp scenario root (no Mongo)."""

import json
from pathlib import Path

import pytest

from fit_ctf.components.types import PathDict
from fit_ctf.models.infra.scenario_manager import ScenarioManager
from fit_ctf.models.utils.exceptions import ScenarioExistException
from fit_ctf.path_mgmt import PathManagement
from fit_ctf_admin.exceptions import AdminError
from fit_ctf_admin.scenario.design_model import ScenarioDesign, VolumeSlot
from fit_ctf_admin.scenario.writer import SIDECAR_NAME, ScenarioWriter


@pytest.fixture
def scenario_mgr(tmp_path: Path) -> ScenarioManager:
    paths = PathDict(
        projects=tmp_path / "project",
        users=tmp_path / "user",
        modules=tmp_path / "module",
        scenarios=tmp_path / "scenario",
    )
    (tmp_path / "scenario").mkdir(parents=True)
    return ScenarioManager(PathManagement(paths))


@pytest.fixture
def writer(scenario_mgr: ScenarioManager) -> ScenarioWriter:
    return ScenarioWriter(scenario_mgr)


def _design(name: str = "designed", target_kind: str = "user") -> ScenarioDesign:
    design = ScenarioDesign(name=name, target_kind=target_kind)  # type: ignore[arg-type]
    block = design.add_block("web", module_name="template")
    design.set_service_key(block.id, "web")
    block.ports = {"http": 8080}
    block.env_keys = ["ADMIN"]
    design.add_secret("flag_main")
    block.volumes.append(
        VolumeSlot(
            name="cfg",
            container_path="/cfg",
            kind="template",
            body="flag={{ secret_map__flag_main }}\n",
        )
    )
    return design


class TestSave:
    def test_save_writes_compose_volumes_and_sidecar(self, writer, scenario_mgr):
        warnings = writer.save(_design())
        assert warnings == []
        scenario_dir = scenario_mgr.get_scenario_dir("designed")
        compose = (scenario_dir / "scenario_compose.yaml.j2").read_text()
        assert "web__port_map__http" in compose
        assert "web__env_map__ADMIN" in compose
        assert "{{ web__volume_map__cfg }}:/cfg:ro" in compose
        assert 'name: "{{ project_name }}_{{ username }}_designed"' in compose
        assert (scenario_dir / "volumes" / "cfg.template").read_text().startswith("flag=")
        payload = json.loads((scenario_dir / SIDECAR_NAME).read_text())
        assert payload["design"]["name"] == "designed"

    def test_written_scenario_is_assignable(self, writer, scenario_mgr):
        writer.save(_design())
        assert scenario_mgr.fetch_secret_keys("designed") == ["flag_main"]
        scaffold = scenario_mgr.fetch_variables("designed")
        assert set(scaffold["web"]["port_map"]) == {"http"}
        assert set(scaffold["web"]["volume_map"]) == {"cfg"}

    def test_project_target_has_no_username_in_name(self, writer, scenario_mgr):
        writer.save(_design(name="prj_scoped", target_kind="project"))
        compose = scenario_mgr.read_compose_template("prj_scoped")
        assert 'name: "{{ project_name }}_prj_scoped"' in compose
        assert "username" not in compose

    def test_wrong_network_for_target_is_rejected(self, writer):
        design = _design(target_kind="project")
        design.blocks[0].networks = ["shared", "private"]
        with pytest.raises(AdminError):
            writer.save(design)

    def test_empty_design_is_rejected(self, writer):
        with pytest.raises(AdminError):
            writer.save(ScenarioDesign(name="empty"))

    def test_self_check_warns_on_unreferenced_secret(self, writer):
        design = _design()
        design.blocks[0].volumes.clear()  # nothing references secret_map__flag_main now
        warnings = writer.save(design)
        assert any("flag_main" in warning for warning in warnings)


class TestCollisions:
    def test_states(self, writer, scenario_mgr):
        assert writer.collision_state("designed") == "new"
        writer.save(_design())
        assert writer.collision_state("designed") == "ours"
        # outside edit invalidates the sidecar hash
        path = scenario_mgr.get_scenario_dir("designed") / "scenario_compose.yaml.j2"
        path.write_text(path.read_text() + "# edited by hand\n")
        assert writer.collision_state("designed") == "foreign"

    def test_save_over_existing_requires_overwrite(self, writer):
        writer.save(_design())
        with pytest.raises(ScenarioExistException):
            writer.save(_design())
        writer.save(_design(), overwrite=True)

    def test_foreign_scenario_without_sidecar(self, writer, scenario_mgr):
        scenario_mgr.save_scenario_files("handmade", "---\nname: x\nservices: {}\n")
        assert writer.collision_state("handmade") == "foreign"


class TestLoad:
    def test_sidecar_roundtrip(self, writer):
        original = _design()
        writer.save(original)
        result = writer.load("designed")
        assert result.fidelity == "sidecar"
        assert result.design is not None
        assert result.design.model_dump() == original.model_dump()

    def test_foreign_scenario_falls_back_to_import_or_raw(self, writer, scenario_mgr):
        scenario_mgr.save_scenario_files(
            "handmade",
            '---\nname: "{{ project_name }}_{{ username }}_handmade"\n\n'
            "services:\n  svc_a:\n    image: fit-ctf/template:latest\n"
            "    networks:\n      {{ network_map__shared }}:\n",
        )
        result = writer.load("handmade")
        assert result.fidelity in ("imported", "raw")
        assert "handmade" in result.compose_text
