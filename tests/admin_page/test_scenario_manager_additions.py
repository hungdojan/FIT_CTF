"""Unit tests for the ScenarioManager additions (no MongoDB needed)."""

from pathlib import Path

import pytest

from fit_ctf.components.types import PathDict
from fit_ctf.models.infra.scenario_manager import ScenarioManager
from fit_ctf.models.utils.exceptions import (
    CTFModelException,
    ScenarioExistException,
    ScenarioNotExistException,
)
from fit_ctf.path_mgmt import PathManagement

COMPOSE = """---
name: "{{ project_name }}_demo"

services:
  web:
    image: fit-ctf/template:latest
    networks:
      {{ network_map__shared }}:
    ports:
      - "{{ web__port_map__http }}:80"
    environment:
      - "ADMIN={{ web__env_map__ADMIN }}"
      - "MODE={{ run_mode }}"
    volumes:
      - "{{ web__volume_map__cfg }}:/cfg:ro"

networks:
  {{ network_map__shared }}:
    external: true
"""

VOLUME_TEMPLATE = "flag={{ secret_map__flag_main }}\nparam={{ web__volume_map__cfg__greeting }}\n"


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


class TestValidateScenarioName:
    @pytest.mark.parametrize("name", ["demo", "demo_2", "a1_b2"])
    def test_valid(self, name):
        ScenarioManager.validate_scenario_name(name)

    @pytest.mark.parametrize("name", ["", "Demo", "de mo", "../etc", "de/mo", "de-mo"])
    def test_invalid(self, name):
        with pytest.raises(CTFModelException):
            ScenarioManager.validate_scenario_name(name)

    def test_get_scenario_dir_rejects_traversal(self, scenario_mgr):
        with pytest.raises(CTFModelException):
            scenario_mgr.get_scenario_dir("../outside")

    def test_create_scenario_rejects_bad_name(self, scenario_mgr):
        with pytest.raises(CTFModelException):
            scenario_mgr.create_scenario("../evil")


class TestSaveScenarioFiles:
    def test_writes_all_files(self, scenario_mgr):
        path = scenario_mgr.save_scenario_files(
            "demo",
            COMPOSE,
            volume_files={"cfg.template": VOLUME_TEMPLATE},
            extra_files={"admin_design.json": "{}"},
        )
        assert (path / "scenario_compose.yaml.j2").read_text() == COMPOSE
        assert (path / "volumes" / "cfg.template").read_text() == VOLUME_TEMPLATE
        assert (path / "admin_design.json").read_text() == "{}"
        assert scenario_mgr.read_compose_template("demo") == COMPOSE

    def test_written_scenario_promises_match(self, scenario_mgr):
        scenario_mgr.save_scenario_files(
            "demo", COMPOSE, volume_files={"cfg.template": VOLUME_TEMPLATE}
        )
        scaffold = scenario_mgr.fetch_variables("demo")
        assert set(scaffold.keys()) == {"web"}
        assert set(scaffold["web"]["env_map"].keys()) == {"ADMIN"}
        assert set(scaffold["web"]["port_map"].keys()) == {"http"}
        assert set(scaffold["web"]["volume_map"].keys()) == {"cfg"}
        assert scenario_mgr.fetch_secret_keys("demo") == ["flag_main"]
        assert scenario_mgr.fetch_unmapped_variables("demo") == {"run_mode"}

    def test_existing_scenario_requires_overwrite(self, scenario_mgr):
        scenario_mgr.save_scenario_files("demo", COMPOSE)
        with pytest.raises(ScenarioExistException):
            scenario_mgr.save_scenario_files("demo", COMPOSE)
        scenario_mgr.save_scenario_files("demo", COMPOSE + "# v2\n", overwrite=True)
        assert scenario_mgr.read_compose_template("demo").endswith("# v2\n")

    def test_unrelated_existing_files_survive_overwrite(self, scenario_mgr):
        path = scenario_mgr.save_scenario_files(
            "demo", COMPOSE, volume_files={"cfg.template": VOLUME_TEMPLATE}
        )
        (path / "volumes" / "handwritten.txt").write_text("keep me")
        scenario_mgr.save_scenario_files("demo", COMPOSE, overwrite=True)
        assert (path / "volumes" / "handwritten.txt").read_text() == "keep me"

    def test_traversal_file_name_rejected_and_cleaned_up(self, scenario_mgr):
        with pytest.raises(CTFModelException):
            scenario_mgr.save_scenario_files("demo", COMPOSE, volume_files={"../evil.txt": "x"})
        # freshly-created scenario dir is removed on failure
        with pytest.raises(ScenarioNotExistException):
            scenario_mgr.get_scenario_dir("demo")

    def test_invalid_name_rejected(self, scenario_mgr):
        with pytest.raises(CTFModelException):
            scenario_mgr.save_scenario_files("../evil", COMPOSE)


class TestFetchUnmappedVariables:
    def test_compile_supplied_variables_are_excluded(self, scenario_mgr):
        extra = (
            'MODE={{ run_mode }}"\n      - "LOGIN={{ login_node_module }}"\n'
            '      - "USER={{ username }}'
        )
        compose = COMPOSE.replace("MODE={{ run_mode }}", extra)
        scenario_mgr.save_scenario_files("demo", compose)
        assert scenario_mgr.fetch_unmapped_variables("demo") == {"run_mode"}

    def test_missing_compose_raises(self, scenario_mgr):
        with pytest.raises(ScenarioNotExistException):
            scenario_mgr.fetch_unmapped_variables("ghost")
