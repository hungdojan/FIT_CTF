"""Gateway protocols — the contract between the UI and both backends.

Every method is a coroutine returning DTOs from :mod:`fit_ctf_admin.dto`
and raising only :class:`~fit_ctf_admin.exceptions.AdminError`. The UI
awaits gateway calls inside Textual workers, so one rule covers slow container
operations and blocking Mongo queries alike.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from fit_ctf.components.types import UserRole
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


@runtime_checkable
class UsersGateway(Protocol):
    async def list_users(self, include_inactive: bool = False) -> list[UserRow]: ...

    async def create_user(
        self,
        username: str,
        password: str | None,
        *,
        generate_password: bool,
        email: str = "",
        role: UserRole = UserRole.USER,
    ) -> tuple[UserRow, str]:
        """Create a user; return the row and the plaintext password (shown once)."""
        ...

    async def change_password(self, username: str, password: str) -> None: ...

    async def disable_user(self, username: str) -> None: ...

    async def delete_user(self, username: str) -> None: ...


@runtime_checkable
class ProjectsGateway(Protocol):
    async def list_projects(self, include_inactive: bool = False) -> list[ProjectRow]: ...

    async def create_project(
        self,
        name: str,
        max_nof_users: int,
        starting_port_bind: int = -1,
        description: str = "",
    ) -> ProjectRow: ...

    async def disable_project(self, name: str) -> None: ...

    async def delete_project(self, name: str) -> None: ...

    async def reserved_ports(self) -> list[PortRangeRow]: ...

    async def export_project(self, name: str, output_path: str) -> str:
        """Export the project as a ZIP archive; returns the written path."""
        ...


@runtime_checkable
class EnrollmentsGateway(Protocol):
    async def list_enrollments(
        self, project_name: str, include_inactive: bool = False
    ) -> list[EnrollmentRow]: ...

    async def list_all_enrollments(self, include_inactive: bool = False) -> list[EnrollmentRow]: ...

    async def enrollable_users(self, project_name: str) -> list[str]:
        """Usernames of active users not yet enrolled in the project."""
        ...

    async def enroll_user(self, username: str, project_name: str) -> EnrollmentRow: ...

    async def cancel_enrollment(self, username: str, project_name: str) -> None: ...


@runtime_checkable
class ClustersGateway(Protocol):
    async def list_project_clusters(self) -> list[ClusterRow]: ...

    async def list_user_clusters(self, project_name: str) -> list[ClusterRow]: ...

    async def start_project_cluster(self, project_name: str) -> None: ...

    async def stop_project_cluster(self, project_name: str) -> None: ...

    async def restart_project_cluster(self, project_name: str) -> None: ...

    async def project_cluster_health(self, project_name: str) -> list[HealthRow]: ...

    async def start_user_cluster(self, username: str, project_name: str) -> None: ...

    async def stop_user_cluster(self, username: str, project_name: str) -> None: ...

    async def restart_user_cluster(self, username: str, project_name: str) -> None: ...

    async def user_cluster_health(self, username: str, project_name: str) -> list[HealthRow]: ...

    async def stop_all_user_clusters(self, project_name: str) -> None: ...


@runtime_checkable
class ScenariosGateway(Protocol):
    """Scenario templates and their assignment to clusters.

    ``kind``/``project_name``/``username`` triplets identify a target cluster
    (``username`` is ``None`` for project clusters). Draft dicts use the
    canonical ``{"secrets", "service_configs", "config_params"}`` shape shared
    with the CLI editor flow.
    """

    async def list_scenarios(self) -> list[ScenarioSummary]: ...

    async def create_scenario(self, name: str) -> None: ...

    async def delete_scenario(self, name: str) -> None: ...

    async def assigned_scenarios(
        self, kind: str, project_name: str, username: str | None = None
    ) -> list[str]: ...

    async def scenario_config_draft(
        self, kind: str, project_name: str, username: str | None, scenario: str
    ) -> dict: ...

    async def validate_scenario_config(
        self, scenario: str, raw: dict
    ) -> tuple[list[str], list[str]]: ...

    async def apply_scenario_config(
        self,
        kind: str,
        project_name: str,
        username: str | None,
        scenario: str,
        raw: dict,
    ) -> list[str]: ...

    async def compile_scenario(
        self, kind: str, project_name: str, username: str | None, scenario: str
    ) -> list[str]: ...

    async def unassign_scenario(
        self, kind: str, project_name: str, username: str | None, scenario: str
    ) -> None: ...

    async def compiled_scenario_preview(self, scenario: str, raw: dict) -> str:
        """Best-effort render of the compose template with the draft's values."""
        ...


@runtime_checkable
class DesignerGateway(Protocol):
    """Scenario designer: module catalog, design load/save, raw template edit.

    Designs travel as JSON strings (``ScenarioDesign.to_json``) so the protocol
    stays serialization-friendly. ``designer_state`` returns ``"new"``,
    ``"ours"`` (sidecar matches the compose template) or ``"foreign"``
    (hand-written or edited outside the designer).
    """

    async def list_module_names(self) -> list[str]: ...

    async def designer_state(self, name: str) -> str: ...

    async def designer_load(self, name: str) -> tuple[str | None, str, str]:
        """Return ``(design_json | None, compose_text, fidelity)``."""
        ...

    async def designer_save(self, design_json: str, *, overwrite: bool = False) -> list[str]:
        """Write the design as a scenario; return self-check warnings."""
        ...

    async def read_raw_template(self, name: str) -> str: ...

    async def save_raw_template(self, name: str, text: str) -> None: ...


@runtime_checkable
class ProgressGateway(Protocol):
    async def leaderboard(self, project_name: str) -> list[LeaderboardRow]: ...

    async def solved_secrets(self, username: str, project_name: str) -> list[SolvedSecretRow]: ...

    async def submission_log(self, username: str, project_name: str) -> list[SubmissionRow]: ...


@runtime_checkable
class LogsGateway(Protocol):
    async def project_cluster_logs(self, project_name: str, tail: int = 500) -> str: ...

    async def user_cluster_logs(self, username: str, project_name: str, tail: int = 500) -> str: ...


@runtime_checkable
class SessionsGateway(Protocol):
    """Login/instance activity from the DB; SSH activity is best-effort.

    SSH rows are parsed out of the login-node container logs, so they only
    exist while the user's cluster is running and logging sshd output.
    """

    async def user_sessions(self, username: str) -> list[SessionRow]: ...

    async def project_sessions(self, project_name: str) -> list[SessionRow]: ...

    async def ssh_activity(
        self, username: str, project_name: str, tail: int = 2000
    ) -> list[SessionRow]: ...


@runtime_checkable
class ModulesGateway(Protocol):
    async def list_modules(self) -> list[ModuleRow]: ...

    async def create_module(self, name: str) -> None: ...

    async def build_module(self, name: str) -> tuple[bool, str]:
        """Build the module image; returns ``(success, build output text)``."""
        ...

    async def remove_module(self, name: str) -> None: ...

    async def list_module_files(self, name: str) -> list[str]: ...

    async def read_module_file(self, name: str, file_name: str) -> str: ...

    async def save_module_file(self, name: str, file_name: str, text: str) -> None: ...


class AdminGateway(
    UsersGateway,
    ProjectsGateway,
    EnrollmentsGateway,
    ClustersGateway,
    ScenariosGateway,
    DesignerGateway,
    ModulesGateway,
    ProgressGateway,
    LogsGateway,
    SessionsGateway,
    Protocol,
):
    """Composite protocol implemented by LiveGateway and PreviewGateway."""
