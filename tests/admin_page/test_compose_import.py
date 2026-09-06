"""Tests for scenario compose import."""

from pathlib import Path

import pytest

from fit_ctf_admin.scenario.compose_export import export_compose_preview
from fit_ctf_admin.scenario.compose_import import (
    ADMIN_DESIGN_NAME,
    ScenarioComposeImporter,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
TEMPLATE_COMPOSE = (
    Path(__file__).resolve().parents[2]
    / "src/fit_ctf/templates/v1/scenarios/template/scenario_compose.yaml.j2"
)
S_FULL_COMPOSE = FIXTURES / "injected_scenarios/s_full/scenario_compose.yaml.j2"
LOGIN_NODE_COMPOSE = (
    Path(__file__).resolve().parents[2]
    / "src/fit_ctf/templates/v1/scenarios/login_node/scenario_compose.yaml.j2"
)


def test_import_template_scenario():
    design = ScenarioComposeImporter(path=TEMPLATE_COMPOSE).import_design(
        scenario_name_fallback="template",
    )

    assert design.name == "template"
    assert len(design.blocks) == 1
    block = design.blocks[0]
    assert block.service_key == "template_service"
    assert block.service_key_mode == "concrete"
    assert block.module_name == "template"
    assert block.networks == ["shared"]
    assert block.ports == {"mongodb": 27017}
    assert block.env_keys == ["ADMIN", "PASSWORD"]


def test_import_s_full_fixture():
    design = ScenarioComposeImporter(path=S_FULL_COMPOSE).import_design(
        scenario_name_fallback="full",
    )

    assert design.name == "full"
    block = design.blocks[0]
    assert block.service_key == "web"
    assert block.module_name == "template"
    assert block.ports == {"http": 80}
    assert block.env_keys == ["FLAG"]


def test_import_login_node_module_default():
    design = ScenarioComposeImporter(path=LOGIN_NODE_COMPOSE).import_design(
        scenario_name_fallback="login_node",
    )

    assert design.name == "login_node"
    block = design.blocks[0]
    assert block.service_key == "login_node"
    assert block.module_name == "ssh_ubi"
    assert block.networks == ["shared", "private"]


def test_import_from_scenario_dir(tmp_path: Path):
    scenario_dir = tmp_path / "demo_challenge"
    scenario_dir.mkdir()
    scenario_dir.joinpath("scenario_compose.yaml.j2").write_text(
        S_FULL_COMPOSE.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    overlay = ScenarioComposeImporter(path=S_FULL_COMPOSE).import_design()
    overlay.blocks[0].label = "Public web"
    overlay.blocks[0].x = 20
    overlay.blocks[0].y = 12
    overlay.save(scenario_dir / ADMIN_DESIGN_NAME)

    design = ScenarioComposeImporter.import_scenario_dir(scenario_dir)

    assert design.blocks[0].label == "Public web"
    assert design.blocks[0].x == 20
    assert design.blocks[0].y == 12


def test_import_requires_path_or_text():
    with pytest.raises(ValueError, match="exactly one"):
        ScenarioComposeImporter()


def test_import_missing_compose_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        ScenarioComposeImporter.from_scenario_dir(tmp_path / "missing")


def test_import_roundtrip_core_fields():
    original = ScenarioComposeImporter(path=TEMPLATE_COMPOSE).import_design()
    preview = export_compose_preview(original)

    assert "template_service:" in preview
    assert "template_service__port_map__mongodb" in preview
    assert "template_service__env_map__ADMIN" in preview
