"""Gateway implementation over the in-memory :class:`PreviewStore`.

Implements the same protocol as :class:`LiveGateway`, so every page (and every
pilot test) runs against it without a database or container runtime.
"""

from __future__ import annotations

from fit_ctf.components.types import UserRole
from fit_ctf_admin.core.passwords import resolve_new_password
from fit_ctf_admin.core.preview_store import PreviewStore
from fit_ctf_admin.core.ssh_activity import parse_ssh_activity
from fit_ctf_admin.core.validation import required
from fit_ctf_admin.dto import (
    ClusterRow,
    EnrollmentRow,
    HealthRow,
    LeaderboardRow,
    ModuleRow,
    PortRangeRow,
    ProjectRow,
    ScenarioSummary,
    SessionRow,
    SolvedSecretRow,
    SubmissionRow,
    UserRow,
)
from fit_ctf_admin.exceptions import AdminError
from fit_ctf_admin.scenario.compiled_preview import render_compiled_preview
from fit_ctf_admin.scenario.design_model import FALLBACK_MODULE_NAMES
from fit_ctf_admin.scenario.draft import normalize_draft


class PreviewGateway:
    """Implements :class:`~fit_ctf_admin.core.protocols.AdminGateway` in memory."""

    def __init__(self, store: PreviewStore | None = None) -> None:
        self.store = store if store is not None else PreviewStore.with_sample_data()

    # -- users ------------------------------------------------------------

    async def list_users(self, include_inactive: bool = False) -> list[UserRow]:
        return self.store.list_users(include_inactive)

    async def create_user(
        self,
        username: str,
        password: str | None,
        *,
        generate_password: bool,
        email: str = "",
        role: UserRole = UserRole.USER,
    ) -> tuple[UserRow, str]:
        username = required(username, "Username")
        plain_password = resolve_new_password(password, generate_password)
        row = self.store.create_user(username, plain_password, email=email.strip(), role=role)
        return row, plain_password

    async def change_password(self, username: str, password: str) -> None:
        plain_password = resolve_new_password(password, generate=False)
        self.store.change_password(username, plain_password)

    async def disable_user(self, username: str) -> None:
        self.store.disable_user(username)

    async def delete_user(self, username: str) -> None:
        self.store.delete_user(username)

    # -- projects ---------------------------------------------------------

    async def list_projects(self, include_inactive: bool = False) -> list[ProjectRow]:
        return self.store.list_projects(include_inactive)

    async def create_project(
        self,
        name: str,
        max_nof_users: int,
        starting_port_bind: int = -1,
        description: str = "",
    ) -> ProjectRow:
        name = required(name, "Project name")
        if max_nof_users < 1:
            raise AdminError("Capacity must be at least 1.")
        return self.store.create_project(name, max_nof_users, starting_port_bind, description)

    async def disable_project(self, name: str) -> None:
        self.store.disable_project(name)

    async def delete_project(self, name: str) -> None:
        self.store.delete_project(name)

    async def reserved_ports(self) -> list[PortRangeRow]:
        return self.store.reserved_ports()

    async def export_project(self, name: str, output_path: str) -> str:
        raise AdminError("Export needs a connected database — not available in preview mode.")

    # -- enrollments ------------------------------------------------------

    async def list_enrollments(
        self, project_name: str, include_inactive: bool = False
    ) -> list[EnrollmentRow]:
        return self.store.list_enrollments(project_name, include_inactive)

    async def list_all_enrollments(self, include_inactive: bool = False) -> list[EnrollmentRow]:
        return self.store.list_all_enrollments(include_inactive)

    async def enrollable_users(self, project_name: str) -> list[str]:
        return self.store.enrollable_users(project_name)

    async def enroll_user(self, username: str, project_name: str) -> EnrollmentRow:
        username = required(username, "Username")
        project_name = required(project_name, "Project name")
        return self.store.enroll_user(username, project_name)

    async def cancel_enrollment(self, username: str, project_name: str) -> None:
        self.store.cancel_enrollment(username, project_name)

    # -- clusters -----------------------------------------------------------

    async def list_project_clusters(self) -> list[ClusterRow]:
        return self.store.list_project_clusters()

    async def list_user_clusters(self, project_name: str) -> list[ClusterRow]:
        return self.store.list_user_clusters(project_name)

    async def start_project_cluster(self, project_name: str) -> None:
        self.store.set_project_cluster_running(project_name, True)

    async def stop_project_cluster(self, project_name: str) -> None:
        self.store.set_project_cluster_running(project_name, False)

    async def restart_project_cluster(self, project_name: str) -> None:
        self.store.set_project_cluster_running(project_name, True)

    async def project_cluster_health(self, project_name: str) -> list[HealthRow]:
        return self.store.project_cluster_health(project_name)

    async def start_user_cluster(self, username: str, project_name: str) -> None:
        # user clusters need their project cluster up, mirroring the live behavior
        self.store.set_project_cluster_running(project_name, True)
        self.store.set_user_cluster_running(username, project_name, True)

    async def stop_user_cluster(self, username: str, project_name: str) -> None:
        self.store.set_user_cluster_running(username, project_name, False)

    async def restart_user_cluster(self, username: str, project_name: str) -> None:
        await self.start_user_cluster(username, project_name)

    async def user_cluster_health(self, username: str, project_name: str) -> list[HealthRow]:
        return self.store.user_cluster_health(username, project_name)

    async def stop_all_user_clusters(self, project_name: str) -> None:
        self.store.stop_all_user_clusters(project_name)

    # -- scenarios ----------------------------------------------------------

    async def list_scenarios(self) -> list[ScenarioSummary]:
        return self.store.list_scenarios()

    async def create_scenario(self, name: str) -> None:
        self.store.create_scenario(name)

    async def delete_scenario(self, name: str) -> None:
        self.store.delete_scenario(name)

    async def assigned_scenarios(
        self, kind: str, project_name: str, username: str | None = None
    ) -> list[str]:
        return self.store.assigned_scenarios(kind, project_name, username)

    async def scenario_config_draft(
        self, kind: str, project_name: str, username: str | None, scenario: str
    ) -> dict:
        return self.store.scenario_config_draft(kind, project_name, username, scenario)

    async def validate_scenario_config(
        self, scenario: str, raw: dict
    ) -> tuple[list[str], list[str]]:
        return self.store.validate_scenario_config(scenario, raw)

    async def apply_scenario_config(
        self,
        kind: str,
        project_name: str,
        username: str | None,
        scenario: str,
        raw: dict,
    ) -> list[str]:
        return self.store.apply_scenario_config(kind, project_name, username, scenario, raw)

    async def compile_scenario(
        self, kind: str, project_name: str, username: str | None, scenario: str
    ) -> list[str]:
        return self.store.compile_scenario(kind, project_name, username, scenario)

    async def unassign_scenario(
        self, kind: str, project_name: str, username: str | None, scenario: str
    ) -> None:
        self.store.unassign_scenario(kind, project_name, username, scenario)

    async def compiled_scenario_preview(self, scenario: str, raw: dict) -> str:
        compose_text = self.store.read_raw_template(scenario)
        normalized, errors = normalize_draft(raw)
        if errors:
            return "# Fix the config first:\n" + "".join(f"#   {e}\n" for e in errors)
        return render_compiled_preview(compose_text, normalized)

    # -- designer -----------------------------------------------------------

    async def list_module_names(self) -> list[str]:
        return sorted(self.store.modules) or list(FALLBACK_MODULE_NAMES)

    async def designer_state(self, name: str) -> str:
        return self.store.designer_state(name)

    async def designer_load(self, name: str) -> tuple[str | None, str, str]:
        return self.store.designer_load(name)

    async def designer_save(self, design_json: str, *, overwrite: bool = False) -> list[str]:
        return self.store.designer_save(design_json, overwrite=overwrite)

    async def read_raw_template(self, name: str) -> str:
        return self.store.read_raw_template(name)

    async def save_raw_template(self, name: str, text: str) -> None:
        self.store.save_raw_template(name, text)

    # -- modules ------------------------------------------------------------

    async def list_modules(self) -> list[ModuleRow]:
        return self.store.list_modules()

    async def create_module(self, name: str) -> None:
        self.store.create_module(name)

    async def build_module(self, name: str) -> tuple[bool, str]:
        if name not in self.store.modules:
            raise AdminError(f"Module `{name}` was not found.")
        return True, f"# preview mode — image fit-ctf/{name} not actually built\n"

    async def list_module_files(self, name: str) -> list[str]:
        return self.store.list_module_files(name)

    async def read_module_file(self, name: str, file_name: str) -> str:
        return self.store.read_module_file(name, file_name)

    async def save_module_file(self, name: str, file_name: str, text: str) -> None:
        self.store.save_module_file(name, file_name, text)

    async def remove_module(self, name: str) -> None:
        self.store.remove_module(name)

    # -- progress / logs / sessions ------------------------------------------

    async def leaderboard(self, project_name: str) -> list[LeaderboardRow]:
        return self.store.leaderboard(project_name)

    async def solved_secrets(self, username: str, project_name: str) -> list[SolvedSecretRow]:
        return self.store.solved_secrets(username, project_name)

    async def submission_log(self, username: str, project_name: str) -> list[SubmissionRow]:
        return self.store.submission_log(username, project_name)

    async def project_cluster_logs(self, project_name: str, tail: int = 500) -> str:
        self.store._project(project_name)
        return self.store.cluster_logs(f"project:{project_name}")

    async def user_cluster_logs(self, username: str, project_name: str, tail: int = 500) -> str:
        return self.store.cluster_logs(f"user:{username}@{project_name}")

    async def user_sessions(self, username: str) -> list[SessionRow]:
        self.store._user(username)
        return self.store.session_rows(username, None)

    async def project_sessions(self, project_name: str) -> list[SessionRow]:
        return self.store.session_rows(None, project_name)

    async def ssh_activity(
        self, username: str, project_name: str, tail: int = 2000
    ) -> list[SessionRow]:
        text = self.store.cluster_logs(f"user:{username}@{project_name}")
        return parse_ssh_activity(username, text)
