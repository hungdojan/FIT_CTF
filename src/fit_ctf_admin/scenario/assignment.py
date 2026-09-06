"""Assignment of scenarios to clusters — plain-Python service over CTFApp.

Mirrors the CLI's ``add-scenario``/``edit-service``/secret commands: drafts are
prefilled from the scenario templates (or the existing cluster config), then
validated and persisted through ``create_or_update_scenario_config``, which
also compiles. No Textual imports here; the gateway calls these methods inside
``asyncio.to_thread``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from fit_ctf.exceptions import CTFBaseException
from fit_ctf_admin.exceptions import AdminError
from fit_ctf_admin.scenario.draft import (
    config_to_draft,
    draft_to_config,
    normalize_draft,
    scaffold_draft,
)
from fit_ctf_admin.scenario.secret_macro import expand_secret_macros

if TYPE_CHECKING:
    from fit_ctf.ctf_app import CTFApp

TargetKind = Literal["project", "user"]


@dataclass(frozen=True, slots=True)
class ClusterTarget:
    """A project cluster, or a user cluster identified by user + project."""

    kind: TargetKind
    project_name: str
    username: str | None = None

    def describe(self) -> str:
        if self.kind == "project":
            return f"project cluster `{self.project_name}`"
        return f"cluster of `{self.username}` in `{self.project_name}`"


class AssignmentService:
    def __init__(self, ctf_app: "CTFApp") -> None:
        self._app = ctf_app

    def _resolve(self, target: ClusterTarget) -> tuple[Any, Any]:
        """Return ``(cluster_mgr, cluster)`` for the target (correlated pair)."""
        project = self._app.prj_mgr.get_project(target.project_name)
        if target.kind == "project":
            mgr = self._app.project_cluster_mgr
            return mgr, mgr.get_cluster(project)
        if not target.username:
            raise AdminError("Select a user for the user cluster target.")
        user = self._app.user_mgr.get_user(target.username)
        enrollment = self._app.enroll_mgr.get_enrollment(user, project)
        mgr = self._app.user_cluster_mgr
        return mgr, mgr.get_cluster(enrollment)

    def assigned_scenarios(self, target: ClusterTarget) -> list[str]:
        _, cluster = self._resolve(target)
        return sorted(cluster.scenario_configs.keys())

    def draft_for(self, target: ClusterTarget, scenario_name: str) -> dict:
        """Editable draft: the existing assigned config, or a template scaffold."""
        _, cluster = self._resolve(target)
        existing = cluster.scenario_configs.get(scenario_name)
        if existing is not None:
            return config_to_draft(existing)
        scenario_mgr = self._app.scenario_mgr
        return scaffold_draft(
            scenario_mgr.fetch_secret_keys(scenario_name),
            scenario_mgr.fetch_variables(scenario_name),
            scenario_mgr.fetch_unmapped_variables(scenario_name),
        )

    def validate(self, scenario_name: str, raw: dict) -> tuple[list[str], list[str]]:
        """Return ``(errors, warnings)`` without persisting anything."""
        normalized, errors = normalize_draft(raw)
        if errors:
            return errors, []
        try:
            config = draft_to_config(scenario_name, normalized)
            warnings = self._app.scenario_mgr.validate_scenario_config_against_templates(
                scenario_name, config
            )
        except CTFBaseException as exc:
            return self._split_validation_message(str(exc)), []
        return [], warnings

    def apply(self, target: ClusterTarget, scenario_name: str, raw: dict) -> list[str]:
        """Persist the config on the cluster and compile it. Returns warnings.

        ``<gen>`` secret macros are expanded here (apply time), so the stored
        config carries the concrete generated values.
        """
        normalized, errors = normalize_draft(raw)
        if errors:
            raise AdminError("Fix the config first: " + "; ".join(errors))
        normalized["secrets"] = expand_secret_macros(normalized["secrets"])
        config = draft_to_config(scenario_name, normalized)
        mgr, cluster = self._resolve(target)
        warnings: list[str] = []
        mgr.create_or_update_scenario_config(cluster, config, template_warning_sink=warnings.append)
        return warnings

    def compile(self, target: ClusterTarget, scenario_name: str) -> list[str]:
        mgr, cluster = self._resolve(target)
        if scenario_name not in cluster.scenario_configs:
            raise AdminError(f"Scenario `{scenario_name}` is not assigned to {target.describe()}.")
        warnings: list[str] = []
        mgr.compile_scenario(cluster, scenario_name, template_warning_sink=warnings.append)
        return warnings

    def unassign(self, target: ClusterTarget, scenario_name: str) -> None:
        mgr, cluster = self._resolve(target)
        if scenario_name not in cluster.scenario_configs:
            raise AdminError(f"Scenario `{scenario_name}` is not assigned to {target.describe()}.")
        mgr.remove_scenario_config(cluster, scenario_name)

    @staticmethod
    def _split_validation_message(message: str) -> list[str]:
        """Split the manager's '; '-joined validation message back into items."""
        prefix = "Scenario config does not satisfy templates: "
        if message.startswith(prefix):
            message = message[len(prefix) :]
        return [part.strip() for part in message.split(";") if part.strip()]
