"""Integration tests for AssignmentService against the real test MongoDB.

Uses ``connected_data`` (2 projects / 3 users, ``CONTAINER_CLIENT=mock``) and a
scenario written through ``save_scenario_files``, then drives the same
assign→validate→apply→compile→unassign pipeline the CLI uses.
"""

import pytest

from fit_ctf_admin.exceptions import AdminError
from fit_ctf_admin.scenario.assignment import AssignmentService, ClusterTarget
from tests import FixtureData

# only "shared" network: compilable on both user and project clusters
COMPOSE = """---
name: "{{ project_name }}_demo_scn"

services:
  web:
    image: fit-ctf/template:latest
    networks:
      {{ network_map__shared }}:
    ports:
      - "{{ web__port_map__http }}:80"
    environment:
      - "ADMIN={{ web__env_map__ADMIN }}"

networks:
  {{ network_map__shared }}:
    external: true
"""

USER_TARGET = ClusterTarget(kind="user", project_name="prj1", username="user2")
PROJECT_TARGET = ClusterTarget(kind="project", project_name="prj1")


@pytest.fixture
def service(connected_data: FixtureData) -> AssignmentService:
    ctf_app, _ = connected_data
    ctf_app.scenario_mgr.save_scenario_files("demo_scn", COMPOSE)
    return AssignmentService(ctf_app)


def _filled_draft(service: AssignmentService, target: ClusterTarget) -> dict:
    draft = service.draft_for(target, "demo_scn")
    draft["service_configs"]["web"]["port_map"]["http"] = "8080"
    draft["service_configs"]["web"]["env_map"]["ADMIN"] = "root"
    return draft


class TestDraft:
    def test_scaffold_shape(self, service):
        draft = service.draft_for(USER_TARGET, "demo_scn")
        assert draft["secrets"] == {}
        assert set(draft["service_configs"]["web"]["env_map"]) == {"ADMIN"}
        assert set(draft["service_configs"]["web"]["port_map"]) == {"http"}
        assert draft["config_params"] == {}

    def test_validate_reports_empty_port(self, service):
        draft = service.draft_for(USER_TARGET, "demo_scn")
        errors, _ = service.validate("demo_scn", draft)
        assert any("web.port_map.http" in error for error in errors)

    def test_validate_clean_draft(self, service):
        draft = _filled_draft(service, USER_TARGET)
        errors, warnings = service.validate("demo_scn", draft)
        assert errors == []
        assert warnings == []

    def test_validate_extra_secret_warns(self, service):
        draft = _filled_draft(service, USER_TARGET)
        draft["secrets"]["bogus"] = "x"
        errors, warnings = service.validate("demo_scn", draft)
        assert errors == []
        assert any("bogus" in warning for warning in warnings)


class TestApplyCompileUnassign:
    def test_user_cluster_roundtrip(self, connected_data, service):
        ctf_app, _ = connected_data
        service.apply(USER_TARGET, "demo_scn", _filled_draft(service, USER_TARGET))

        user = ctf_app.user_mgr.get_user("user2")
        project = ctf_app.prj_mgr.get_project("prj1")
        enrollment = ctf_app.enroll_mgr.get_enrollment(user, project)
        cluster = ctf_app.user_cluster_mgr.get_cluster(enrollment)
        assert "demo_scn" in cluster.scenario_configs
        assert cluster.scenario_configs["demo_scn"].service_configs["web"].port_map == {
            "http": 8080
        }

        compiled = ctf_app.paths.enrolled_user_path(user, project) / "demo_scn"
        compose_file = compiled / "scenario_compose.yaml"
        assert compose_file.is_file()
        text = compose_file.read_text()
        assert "8080:80" in text and "ADMIN=root" in text and "prj1_demo_scn" in text

        # connected_data user clusters already carry the login_node scenario
        assert "demo_scn" in service.assigned_scenarios(USER_TARGET)
        assert service.compile(USER_TARGET, "demo_scn") == []

        service.unassign(USER_TARGET, "demo_scn")
        cluster = ctf_app.user_cluster_mgr.get_cluster(enrollment)
        assert "demo_scn" not in cluster.scenario_configs
        assert not compiled.exists()

    def test_edit_existing_config(self, connected_data, service):
        ctf_app, _ = connected_data
        service.apply(USER_TARGET, "demo_scn", _filled_draft(service, USER_TARGET))

        draft = service.draft_for(USER_TARGET, "demo_scn")
        assert draft["service_configs"]["web"]["env_map"]["ADMIN"] == "root"
        assert draft["service_configs"]["web"]["port_map"]["http"] == "8080"

        draft["service_configs"]["web"]["env_map"]["ADMIN"] = "operator"
        service.apply(USER_TARGET, "demo_scn", draft)

        user = ctf_app.user_mgr.get_user("user2")
        project = ctf_app.prj_mgr.get_project("prj1")
        compiled = ctf_app.paths.enrolled_user_path(user, project) / "demo_scn"
        assert "ADMIN=operator" in (compiled / "scenario_compose.yaml").read_text()

    def test_project_cluster_roundtrip(self, connected_data, service):
        ctf_app, _ = connected_data
        service.apply(PROJECT_TARGET, "demo_scn", _filled_draft(service, PROJECT_TARGET))

        project = ctf_app.prj_mgr.get_project("prj1")
        cluster = ctf_app.project_cluster_mgr.get_cluster(project)
        assert "demo_scn" in cluster.scenario_configs

        compiled = ctf_app.paths.project_scenarios(project) / "demo_scn"
        assert (compiled / "scenario_compose.yaml").is_file()

        service.unassign(PROJECT_TARGET, "demo_scn")
        assert not compiled.exists()

    def test_apply_with_errors_raises(self, service):
        draft = service.draft_for(USER_TARGET, "demo_scn")  # unfilled ports
        with pytest.raises(AdminError):
            service.apply(USER_TARGET, "demo_scn", draft)

    def test_compile_unassigned_raises(self, service):
        with pytest.raises(AdminError):
            service.compile(USER_TARGET, "demo_scn")

    def test_unknown_user_raises_domain_error(self, service):
        """The raw service raises domain errors; mapping to AdminError is the
        gateway's job (covered in test_gateways.py)."""
        from fit_ctf.models.utils.exceptions import UserNotExistsException

        target = ClusterTarget(kind="user", project_name="prj1", username="ghost")
        with pytest.raises(UserNotExistsException):
            service.draft_for(target, "demo_scn")


class TestSecretMacro:
    def test_gen_macro_expanded_and_persisted(self, connected_data, service):
        """<gen> is resolved at apply time; the concrete value lands in Mongo."""
        import re

        ctf_app, _ = connected_data
        ctf_app.scenario_mgr.save_scenario_files(
            "secret_scn",
            COMPOSE.replace("demo_scn", "secret_scn"),
            volume_files={"flag.template": "flag={{ secret_map__flag_main }}\n"},
        )
        target = ClusterTarget(kind="user", project_name="prj1", username="user2")
        draft = service.draft_for(target, "secret_scn")
        draft["service_configs"]["web"]["port_map"]["http"] = "8080"
        draft["service_configs"]["web"]["env_map"]["ADMIN"] = "root"
        draft["secrets"]["flag_main"] = "FLAG{<gen>}"

        # validation leaves the macro untouched (no randomness consumed)
        errors, _ = service.validate("secret_scn", draft)
        assert errors == []
        assert draft["secrets"]["flag_main"] == "FLAG{<gen>}"

        service.apply(target, "secret_scn", draft)

        user = ctf_app.user_mgr.get_user("user2")
        project = ctf_app.prj_mgr.get_project("prj1")
        enrollment = ctf_app.enroll_mgr.get_enrollment(user, project)
        cluster = ctf_app.user_cluster_mgr.get_cluster(enrollment)
        stored = cluster.scenario_configs["secret_scn"].secrets["flag_main"]
        assert re.fullmatch(r"FLAG\{[A-Za-z0-9]{32}\}", stored), stored

        # re-opening the config shows the concrete value, not the macro
        draft = service.draft_for(target, "secret_scn")
        assert draft["secrets"]["flag_main"] == stored
