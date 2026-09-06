"""Tests for admin page models and compose export."""

from fit_ctf_admin.scenario.compose_export import export_compose_preview
from fit_ctf_admin.scenario.design_model import (
    ScenarioDesign,
    parse_key_value_lines,
    parse_port_lines,
)


def test_add_block_assigns_unique_labels_and_service_keys():
    design = ScenarioDesign(name="demo")
    first = design.add_block()
    second = design.add_block()

    assert first.label == "service_1"
    assert second.label == "service_2"
    assert first.service_key != second.service_key
    assert first.service_key.startswith("svc_")
    assert len(design.blocks) == 2


def test_export_compose_preview_uses_service_key_not_display_name():
    design = ScenarioDesign(name="buffer_overflow", secrets=["flag_main"])
    block = design.add_block(label="Challenge UI", module_name="template")
    block.service_key = "challenge"
    block.service_key_mode = "concrete"
    block.networks = ["private", "operational"]
    design.add_custom_network("db_private", "DB Private")

    preview = export_compose_preview(design)

    assert 'name: "{{ project_name }}_{{ username }}_buffer_overflow"' in preview
    assert "  challenge:" in preview
    assert "Challenge UI:" not in preview
    assert "challenge__port_map__web" in preview
    assert "fit-ctf/template:latest" in preview
    assert "{{ network_map__private }}:" in preview
    assert "secret_map__flag_main" in preview


def test_export_compose_preview_emits_concrete_container_name():
    design = ScenarioDesign(name="demo")
    block = design.add_block(label="web")
    block.container_name_mode = "concrete"
    block.container_name = "web_challenge_ctr"

    preview = export_compose_preview(design)

    assert "container_name: web_challenge_ctr" in preview


def test_custom_network_attached_to_service():
    design = ScenarioDesign(name="custom")
    design.add_custom_network("attacker_vlan", "Attacker VLAN")
    block = design.add_block(label="victim")
    block.networks = ["shared", "attacker_vlan"]

    preview = export_compose_preview(design)
    assert "attacker_vlan:" in preview
    assert "      attacker_vlan:" in preview


def test_design_roundtrip_json(tmp_path):
    design = ScenarioDesign(name="roundtrip", secrets=["flag"])
    design.add_custom_network("extra_private", "Extra Private")
    design.add_block(label="web", module_name="ssh_debian")

    path = tmp_path / "design.json"
    design.save(path)
    loaded = ScenarioDesign.load(path)

    assert loaded.name == "roundtrip"
    assert loaded.secrets == ["flag"]
    assert loaded.custom_networks[0].name == "extra_private"
    assert loaded.blocks[0].label == "web"


def test_block_node_can_place_at_top_of_world():
    from fit_ctf_admin.scenario.design_model import WORLD_HEIGHT, WORLD_WIDTH
    from fit_ctf_admin.widgets.designer.block_node import BlockNode

    blocks = [
        ScenarioDesign(name="x").add_block(label="first"),
        ScenarioDesign(name="x").add_block(label="second"),
    ]
    for block in blocks:
        block.y = 0
        node = BlockNode(block, lambda: (WORLD_WIDTH, WORLD_HEIGHT))
        node._apply_geometry(snap=True)
        assert block.y == 0
        assert node.styles.position == "absolute"


def test_block_can_move_above_service_area():
    from fit_ctf_admin.scenario.design_model import WORLD_HEIGHT, WORLD_WIDTH

    block = ScenarioDesign(name="x").add_block()
    block.y = 0
    block.clamp_position(WORLD_WIDTH, WORLD_HEIGHT)
    assert block.y == 0


def test_add_secret_stores_name_only():
    design = ScenarioDesign(name="demo")
    key = design.add_secret("flag_main")
    assert key == "flag_main"
    assert design.secrets == ["flag_main"]


def test_add_env_stores_key_only():
    design = ScenarioDesign(name="demo")
    block = design.add_block(label="web")
    design.add_env_to_block(block.id, "ADMIN")
    assert block.env_keys == ["ADMIN"]


def test_parse_helpers():
    assert parse_key_value_lines("flag_main=FITCTF{x}\n# comment\nADMIN=root") == {
        "flag_main": "FITCTF{x}",
        "ADMIN": "root",
    }
    assert parse_port_lines("web:8080, api:3000") == {"web": 8080, "api": 3000}
