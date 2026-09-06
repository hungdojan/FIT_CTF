"""Compile-time lint of compiled compose files (docker schema hazards)."""

from fit_ctf.models.infra.utils import lint_compiled_compose
from fit_ctf_admin.scenario.assignment import AssignmentService, ClusterTarget
from tests import FixtureData

# hand-written-style template with an UNQUOTED env entry: renders to
# `- ADMIN: root`, which YAML parses as a mapping -> docker rejects it
BAD_COMPOSE = """---
name: "{{ project_name }}_bad_env"

services:
  web:
    image: fit-ctf/template:latest
    networks:
      {{ network_map__shared }}:
    environment:
      - ADMIN: {{ web__env_map__ADMIN }}

networks:
  {{ network_map__shared }}:
    external: true
"""


class TestLintUnit:
    def test_mapping_entry_is_flagged_with_service_and_index(self):
        compose = {"services": {"web": {"environment": [{"ADMIN": "root"}]}}}
        warnings = lint_compiled_compose(compose)
        assert len(warnings) == 1
        assert "'web'" in warnings[0] and "entry 0" in warnings[0]
        assert '"KEY=value"' in warnings[0]

    def test_string_entries_pass(self):
        compose = {"services": {"web": {"environment": ["ADMIN=root", "X=1"]}}}
        assert lint_compiled_compose(compose) == []

    def test_map_form_environment_passes(self):
        compose = {"services": {"web": {"environment": {"ADMIN": "root"}}}}
        assert lint_compiled_compose(compose) == []

    def test_none_entry_is_flagged(self):
        compose = {"services": {"web": {"environment": [None]}}}
        warnings = lint_compiled_compose(compose)
        assert len(warnings) == 1 and "empty" in warnings[0]

    def test_degenerate_documents_pass(self):
        assert lint_compiled_compose({}) == []
        assert lint_compiled_compose({"services": None}) == []
        assert lint_compiled_compose({"services": {"web": None}}) == []


class TestLintOnCompile:
    def test_apply_surfaces_env_entry_warning(self, connected_data: FixtureData):
        ctf_app, _ = connected_data
        ctf_app.scenario_mgr.save_scenario_files("bad_env", BAD_COMPOSE)
        service = AssignmentService(ctf_app)
        target = ClusterTarget(kind="project", project_name="prj1")

        draft = service.draft_for(target, "bad_env")
        draft["service_configs"]["web"]["env_map"]["ADMIN"] = "root"
        warnings = service.apply(target, "bad_env", draft)

        assert any("'web'" in w and "environment entry" in w for w in warnings)
        # the file is still compiled; the warning is advisory
        project = ctf_app.prj_mgr.get_project("prj1")
        compiled = ctf_app.paths.project_scenarios(project) / "bad_env"
        assert (compiled / "scenario_compose.yaml").is_file()
