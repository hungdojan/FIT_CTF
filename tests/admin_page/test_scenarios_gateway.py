"""Scenario gateway tests over both implementations."""

import pytest

from fit_ctf_admin.core.live_gateway import LiveGateway
from fit_ctf_admin.core.preview_gateway import PreviewGateway
from fit_ctf_admin.core.preview_store import PreviewStore
from fit_ctf_admin.core.protocols import AdminGateway
from fit_ctf_admin.exceptions import AdminError

STRONG_PASSWORD = "StrongPass123"


@pytest.fixture(params=["preview", "live"])
def gateway(request) -> AdminGateway:
    if request.param == "preview":
        return PreviewGateway(PreviewStore())
    ctf_app, _ = request.getfixturevalue("empty_data")
    return LiveGateway(ctf_app)


async def test_create_and_list_scenario(gateway: AdminGateway):
    await gateway.create_scenario("demo_x")
    names = [s.name for s in await gateway.list_scenarios()]
    assert "demo_x" in names


async def test_create_duplicate_scenario_raises(gateway: AdminGateway):
    await gateway.create_scenario("demo_x")
    with pytest.raises(AdminError):
        await gateway.create_scenario("demo_x")


async def test_create_invalid_name_raises(gateway: AdminGateway):
    with pytest.raises(AdminError):
        await gateway.create_scenario("../evil")


async def test_delete_scenario(gateway: AdminGateway):
    await gateway.create_scenario("demo_x")
    await gateway.delete_scenario("demo_x")
    names = [s.name for s in await gateway.list_scenarios()]
    assert "demo_x" not in names


class TestPreviewAssignment:
    @pytest.fixture
    def preview(self) -> PreviewGateway:
        return PreviewGateway(PreviewStore.with_sample_data())

    async def test_delete_assigned_scenario_is_guarded(self, preview):
        with pytest.raises(AdminError):
            await preview.delete_scenario("login_node")

    async def test_assign_edit_unassign_roundtrip(self, preview):
        draft = await preview.scenario_config_draft("project", "intro_linux", None, "web_stack")
        errors, _ = await preview.validate_scenario_config("web_stack", draft)
        assert errors  # unfilled port + secret key is fine, port errors out

        draft["service_configs"]["web"]["port_map"]["http"] = "8080"
        draft["service_configs"]["web"]["env_map"]["ADMIN"] = "admin"
        draft["secrets"]["flag_web"] = "FLAG{x}"
        errors, warnings = await preview.validate_scenario_config("web_stack", draft)
        assert errors == [] and warnings == []

        await preview.apply_scenario_config("project", "intro_linux", None, "web_stack", draft)
        assigned = await preview.assigned_scenarios("project", "intro_linux")
        assert "web_stack" in assigned

        # edit: draft now returns the stored config
        draft = await preview.scenario_config_draft("project", "intro_linux", None, "web_stack")
        assert draft["secrets"]["flag_web"] == "FLAG{x}"

        await preview.unassign_scenario("project", "intro_linux", None, "web_stack")
        assert "web_stack" not in await preview.assigned_scenarios("project", "intro_linux")

    async def test_missing_required_secret_errors(self, preview):
        draft = await preview.scenario_config_draft("project", "intro_linux", None, "web_stack")
        draft["service_configs"]["web"]["port_map"]["http"] = "8080"
        draft["service_configs"]["web"]["env_map"]["ADMIN"] = "admin"
        del draft["secrets"]["flag_web"]
        errors, _ = await preview.validate_scenario_config("web_stack", draft)
        assert any("flag_web" in error for error in errors)


class TestSecretMacroPreview:
    async def test_gen_macro_expanded_on_apply(self):
        import re

        preview = PreviewGateway(PreviewStore.with_sample_data())
        draft = await preview.scenario_config_draft("project", "intro_linux", None, "web_stack")
        draft["service_configs"]["web"]["port_map"]["http"] = "8080"
        draft["service_configs"]["web"]["env_map"]["ADMIN"] = "admin"
        draft["secrets"]["flag_web"] = "FLAG{<gen:16>}"

        await preview.apply_scenario_config("project", "intro_linux", None, "web_stack", draft)
        stored = await preview.scenario_config_draft("project", "intro_linux", None, "web_stack")
        assert re.fullmatch(r"FLAG\{[A-Za-z0-9]{16}\}", stored["secrets"]["flag_web"])
