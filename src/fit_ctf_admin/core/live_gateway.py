"""Gateway implementation backed by a connected :class:`~fit_ctf.ctf_app.CTFApp`.

Two cross-cutting rules are applied by the :func:`guard` decorator:

* ``fit_ctf`` domain errors (``CTFBaseException`` — note: a ``BaseException``
  subclass) and pymongo errors are re-raised as :class:`AdminError` so the UI
  has a single exception surface.
* Methods are coroutines; blocking pymongo/manager calls run in a worker
  thread via :func:`asyncio.to_thread`, while natively async manager methods
  are awaited directly.
"""

from __future__ import annotations

import asyncio
import functools
from pathlib import Path
from typing import Any, Awaitable, Callable, TypeVar

import pymongo.errors

from fit_ctf.components.types import UserRole
from fit_ctf.ctf_app import CTFApp
from fit_ctf.exceptions import CTFBaseException
from fit_ctf.models.utils.exceptions import (
    ProjectClusterNotExistException,
    UserClusterNotExistException,
)
from fit_ctf_admin.core.passwords import resolve_new_password
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
from fit_ctf_admin.exceptions import AdminConnectionError, AdminError
from fit_ctf_admin.scenario.assignment import AssignmentService, ClusterTarget
from fit_ctf_admin.scenario.compiled_preview import render_compiled_preview
from fit_ctf_admin.scenario.design_model import ScenarioDesign
from fit_ctf_admin.scenario.draft import normalize_draft
from fit_ctf_admin.scenario.writer import ScenarioWriter

T = TypeVar("T")


def _format_time(value) -> str:
    """Local, second-precision display format; empty string for missing times."""
    if value is None:
        return ""
    try:
        return value.astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except (AttributeError, ValueError):
        return str(value)


def guard(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
    """Map backend exceptions to :class:`AdminError` on any gateway coroutine."""

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> T:
        try:
            return await func(*args, **kwargs)
        except AdminError:
            raise
        except pymongo.errors.ServerSelectionTimeoutError as exc:
            raise AdminConnectionError(
                "Lost connection to the database. Start MongoDB with `inv db-start`."
            ) from exc
        except pymongo.errors.PyMongoError as exc:
            raise AdminError(str(exc)) from exc
        except CTFBaseException as exc:
            raise AdminError(str(exc)) from exc
        except FileNotFoundError as exc:
            missing = exc.filename or exc
            raise AdminError(
                f"Command not found: `{missing}`. Is the container runtime "
                "(podman/podman-compose or docker) installed and on PATH? "
                "Check CONTAINER_CLIENT in .env."
            ) from exc
        except Exception as exc:  # last resort: never fail silently in the UI
            raise AdminError(f"Unexpected error: {exc}") from exc

    return wrapper


class LiveGateway:
    """Implements :class:`~fit_ctf_admin.core.protocols.AdminGateway` over CTFApp."""

    def __init__(self, ctf_app: CTFApp) -> None:
        self._app = ctf_app

    @property
    def ctf_app(self) -> CTFApp:
        return self._app

    # -- users ------------------------------------------------------------

    @guard
    async def list_users(self, include_inactive: bool = False) -> list[UserRow]:
        active = None if include_inactive else True
        raws = await asyncio.to_thread(self._app.user_mgr.get_users_info, active)
        return [UserRow.from_raw(raw) for raw in raws]

    @guard
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

        def _create() -> tuple[UserRow, str]:
            user, data = self._app.user_mgr.create_new_user(
                username, plain_password, role=role, email=email.strip()
            )
            row = UserRow(
                username=user.username,
                email=user.email,
                role=str(user.role),
                active=user.active,
                projects=(),
            )
            return row, data["password"]

        return await asyncio.to_thread(_create)

    @guard
    async def change_password(self, username: str, password: str) -> None:
        plain_password = resolve_new_password(password, generate=False)
        await asyncio.to_thread(self._app.user_mgr.change_password, username, plain_password)

    @guard
    async def disable_user(self, username: str) -> None:
        await self._app.user_mgr.disable_user(username, self._app.enroll_mgr)

    @guard
    async def delete_user(self, username: str) -> None:
        await self._app.user_mgr.delete_users([username], self._app.enroll_mgr)

    # -- projects ---------------------------------------------------------

    @guard
    async def list_projects(self, include_inactive: bool = False) -> list[ProjectRow]:
        raws = await asyncio.to_thread(self._app.prj_mgr.get_projects_raw, include_inactive)
        return [ProjectRow.from_raw(raw) for raw in raws]

    @guard
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
        project = await asyncio.to_thread(
            self._app.prj_mgr.init_project,
            name,
            max_nof_users,
            starting_port_bind,
            description.strip(),
        )
        return ProjectRow(
            name=project.name,
            max_nof_users=project.max_nof_users,
            active_users=0,
            active=project.active,
        )

    @guard
    async def disable_project(self, name: str) -> None:
        await self._app.prj_mgr.disable_project(name, self._app.enroll_mgr)

    @guard
    async def delete_project(self, name: str) -> None:
        await self._app.prj_mgr.delete_project(name, self._app.enroll_mgr)

    @guard
    async def reserved_ports(self) -> list[PortRangeRow]:
        raws = await asyncio.to_thread(self._app.prj_mgr.get_reserved_ports)
        return [PortRangeRow.from_raw(raw) for raw in raws]

    @guard
    async def export_project(self, name: str, output_path: str) -> str:
        output_path = required(output_path, "Output file")
        target = Path(output_path).expanduser().resolve()
        if target.is_dir():
            raise AdminError(f"`{target}` is a directory — give a file name.")
        target.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(self._app.export_project, name, str(target))
        return str(target)

    # -- enrollments ------------------------------------------------------

    @guard
    async def list_enrollments(
        self, project_name: str, include_inactive: bool = False
    ) -> list[EnrollmentRow]:
        raws = await asyncio.to_thread(
            self._app.enroll_mgr.get_enrollments_for_project_raw,
            project_name,
            include_inactive,
        )
        rows = [EnrollmentRow.from_raw(project_name, raw) for raw in raws]
        rows.sort(key=lambda row: row.username)
        return rows

    @guard
    async def list_all_enrollments(self, include_inactive: bool = False) -> list[EnrollmentRow]:
        def _collect() -> list[EnrollmentRow]:
            rows: list[EnrollmentRow] = []
            for project in self._app.prj_mgr.get_projects_raw(include_inactive):
                raws = self._app.enroll_mgr.get_enrollments_for_project_raw(
                    project["name"], include_inactive
                )
                rows.extend(EnrollmentRow.from_raw(project["name"], raw) for raw in raws)
            rows.sort(key=lambda row: (row.project, row.username))
            return rows

        return await asyncio.to_thread(_collect)

    @guard
    async def enrollable_users(self, project_name: str) -> list[str]:
        def _collect() -> list[str]:
            usernames = [
                user["username"] for user in self._app.user_mgr.get_users_info(active=True)
            ]
            free = self._app.enroll_mgr.filter_users_not_in_project(project_name, usernames)
            return sorted(free)

        return await asyncio.to_thread(_collect)

    @guard
    async def enroll_user(self, username: str, project_name: str) -> EnrollmentRow:
        username = required(username, "Username")
        project_name = required(project_name, "Project name")

        def _enroll() -> EnrollmentRow:
            user = self._app.user_mgr.get_user(username)
            project = self._app.prj_mgr.get_project(project_name)
            enrollment = self._app.enroll_mgr.enroll_user_to_project(user, project)
            return EnrollmentRow(
                username=user.username,
                project=project.name,
                role=str(user.role),
                active=enrollment.active,
                forwarded_port=enrollment.forwarded_port,
            )

        return await asyncio.to_thread(_enroll)

    @guard
    async def cancel_enrollment(self, username: str, project_name: str) -> None:
        await self._app.enroll_mgr.cancel_enrollment(username, project_name)

    # -- clusters -----------------------------------------------------------

    def _project_cluster(self, project_name: str):
        project = self._app.prj_mgr.get_project(project_name)
        return self._app.project_cluster_mgr.get_cluster(project)

    def _user_cluster(self, username: str, project_name: str):
        user = self._app.user_mgr.get_user(username)
        project = self._app.prj_mgr.get_project(project_name)
        enrollment = self._app.enroll_mgr.get_enrollment(user, project)
        return self._app.user_cluster_mgr.get_cluster(enrollment)

    @staticmethod
    def _check_exit_code(code: int, action: str) -> None:
        if code != 0:
            raise AdminError(f"{action} failed (exit code {code}). Check the logs.")

    @guard
    async def list_project_clusters(self) -> list[ClusterRow]:
        projects = await asyncio.to_thread(self._app.prj_mgr.get_projects_raw)
        rows: list[ClusterRow] = []
        for project in projects:
            name = project["name"]
            try:
                cluster = await asyncio.to_thread(self._project_cluster, name)
            except ProjectClusterNotExistException:
                rows.append(ClusterRow("project", name, None, "", False, ()))
                continue
            running = await self._app.project_cluster_mgr.cluster_is_running(cluster)
            rows.append(
                ClusterRow(
                    "project",
                    name,
                    None,
                    cluster.name,
                    running,
                    tuple(cluster.scenario_names),
                )
            )
        return rows

    @guard
    async def list_user_clusters(self, project_name: str) -> list[ClusterRow]:
        enrollments = await asyncio.to_thread(
            self._app.enroll_mgr.get_enrollments_for_project_raw, project_name
        )
        rows: list[ClusterRow] = []
        for enrollment in sorted(enrollments, key=lambda item: item["username"]):
            username = enrollment["username"]
            try:
                cluster = await asyncio.to_thread(self._user_cluster, username, project_name)
            except (UserClusterNotExistException, CTFBaseException):
                rows.append(ClusterRow("user", project_name, username, "", False, ()))
                continue
            running = await self._app.user_cluster_mgr.cluster_is_running(cluster)
            rows.append(
                ClusterRow(
                    "user",
                    project_name,
                    username,
                    cluster.name,
                    running,
                    tuple(cluster.scenario_names),
                )
            )
        return rows

    @guard
    async def start_project_cluster(self, project_name: str) -> None:
        cluster = await asyncio.to_thread(self._project_cluster, project_name)
        code = await self._app.project_cluster_mgr.start_cluster(cluster)
        self._check_exit_code(code, f"Starting project cluster `{project_name}`")

    @guard
    async def stop_project_cluster(self, project_name: str) -> None:
        cluster = await asyncio.to_thread(self._project_cluster, project_name)
        code = await self._app.project_cluster_mgr.stop_cluster(cluster)
        self._check_exit_code(code, f"Stopping project cluster `{project_name}`")

    @guard
    async def restart_project_cluster(self, project_name: str) -> None:
        cluster = await asyncio.to_thread(self._project_cluster, project_name)
        code = await self._app.project_cluster_mgr.restart_cluster(cluster)
        self._check_exit_code(code, f"Restarting project cluster `{project_name}`")

    @guard
    async def project_cluster_health(self, project_name: str) -> list[HealthRow]:
        cluster = await asyncio.to_thread(self._project_cluster, project_name)
        raws = await self._app.project_cluster_mgr.cluster_health_check(cluster)
        return [HealthRow.from_raw(raw) for raw in raws]

    @guard
    async def start_user_cluster(self, username: str, project_name: str) -> None:
        cluster = await asyncio.to_thread(self._user_cluster, username, project_name)
        code = await self._app.user_cluster_mgr.start_cluster(cluster, self._app.enroll_mgr)
        self._check_exit_code(code, f"Starting cluster of `{username}` in `{project_name}`")

    @guard
    async def stop_user_cluster(self, username: str, project_name: str) -> None:
        cluster = await asyncio.to_thread(self._user_cluster, username, project_name)
        code = await self._app.user_cluster_mgr.stop_cluster(cluster, self._app.enroll_mgr)
        self._check_exit_code(code, f"Stopping cluster of `{username}` in `{project_name}`")

    @guard
    async def restart_user_cluster(self, username: str, project_name: str) -> None:
        cluster = await asyncio.to_thread(self._user_cluster, username, project_name)
        code = await self._app.user_cluster_mgr.restart_cluster(cluster, self._app.enroll_mgr)
        self._check_exit_code(code, f"Restarting cluster of `{username}` in `{project_name}`")

    @guard
    async def user_cluster_health(self, username: str, project_name: str) -> list[HealthRow]:
        cluster = await asyncio.to_thread(self._user_cluster, username, project_name)
        raws = await self._app.user_cluster_mgr.cluster_health_check(cluster)
        return [HealthRow.from_raw(raw) for raw in raws]

    @guard
    async def stop_all_user_clusters(self, project_name: str) -> None:
        project = await asyncio.to_thread(self._app.prj_mgr.get_project, project_name)
        await self._app.user_cluster_mgr.stop_all_user_clusters(project, self._app.enroll_mgr)

    # -- scenarios ----------------------------------------------------------

    @property
    def _assignment(self) -> AssignmentService:
        return AssignmentService(self._app)

    @staticmethod
    def _target(kind: str, project_name: str, username: str | None) -> ClusterTarget:
        if kind not in ("project", "user"):
            raise AdminError(f"Unknown cluster kind {kind!r}.")
        return ClusterTarget(kind=kind, project_name=project_name, username=username)

    @guard
    async def list_scenarios(self) -> list[ScenarioSummary]:
        def _collect() -> list[ScenarioSummary]:
            overview = self._app.scenario_mgr.scenario_overview(self._app.user_cluster_mgr)
            return [
                ScenarioSummary(name=name, user_cluster_count=len(clusters))
                for name, clusters in sorted(overview.items())
            ]

        return await asyncio.to_thread(_collect)

    @guard
    async def create_scenario(self, name: str) -> None:
        await asyncio.to_thread(self._app.scenario_mgr.create_scenario, name.strip())

    @guard
    async def delete_scenario(self, name: str) -> None:
        def _delete() -> None:
            used_by_users = self._app.scenario_mgr.scenario_usage(name, self._app.user_cluster_mgr)
            used_by_projects = list(
                self._app.project_cluster_mgr.collection.find(
                    {f"scenario_configs.{name}": {"$exists": True}}
                )
            )
            if used_by_users or used_by_projects:
                raise AdminError(
                    f"Scenario `{name}` is assigned to "
                    f"{len(used_by_users)} user cluster(s) and "
                    f"{len(used_by_projects)} project cluster(s). Unassign it first."
                )
            self._app.scenario_mgr.delete_scenario(name)

        await asyncio.to_thread(_delete)

    @guard
    async def assigned_scenarios(
        self, kind: str, project_name: str, username: str | None = None
    ) -> list[str]:
        target = self._target(kind, project_name, username)
        return await asyncio.to_thread(self._assignment.assigned_scenarios, target)

    @guard
    async def scenario_config_draft(
        self, kind: str, project_name: str, username: str | None, scenario: str
    ) -> dict:
        target = self._target(kind, project_name, username)
        return await asyncio.to_thread(self._assignment.draft_for, target, scenario)

    @guard
    async def validate_scenario_config(
        self, scenario: str, raw: dict
    ) -> tuple[list[str], list[str]]:
        return await asyncio.to_thread(self._assignment.validate, scenario, raw)

    @guard
    async def apply_scenario_config(
        self,
        kind: str,
        project_name: str,
        username: str | None,
        scenario: str,
        raw: dict,
    ) -> list[str]:
        target = self._target(kind, project_name, username)
        return await asyncio.to_thread(self._assignment.apply, target, scenario, raw)

    @guard
    async def compile_scenario(
        self, kind: str, project_name: str, username: str | None, scenario: str
    ) -> list[str]:
        target = self._target(kind, project_name, username)
        return await asyncio.to_thread(self._assignment.compile, target, scenario)

    @guard
    async def unassign_scenario(
        self, kind: str, project_name: str, username: str | None, scenario: str
    ) -> None:
        target = self._target(kind, project_name, username)
        await asyncio.to_thread(self._assignment.unassign, target, scenario)

    @guard
    async def compiled_scenario_preview(self, scenario: str, raw: dict) -> str:
        def _render() -> str:
            compose_text = self._app.scenario_mgr.read_compose_template(scenario)
            normalized, errors = normalize_draft(raw)
            if errors:
                return "# Fix the config first:\n" + "".join(f"#   {e}\n" for e in errors)
            return render_compiled_preview(compose_text, normalized)

        return await asyncio.to_thread(_render)

    # -- designer -----------------------------------------------------------

    @property
    def _writer(self) -> ScenarioWriter:
        return ScenarioWriter(self._app.scenario_mgr)

    @guard
    async def list_module_names(self) -> list[str]:
        modules = await asyncio.to_thread(self._app.module_mgr.list_modules)
        return sorted(modules.keys())

    @guard
    async def designer_state(self, name: str) -> str:
        return await asyncio.to_thread(self._writer.collision_state, name)

    @guard
    async def designer_load(self, name: str) -> tuple[str | None, str, str]:
        result = await asyncio.to_thread(self._writer.load, name)
        design_json = result.design.to_json() if result.design is not None else None
        return design_json, result.compose_text, result.fidelity

    @guard
    async def designer_save(self, design_json: str, *, overwrite: bool = False) -> list[str]:
        try:
            design = ScenarioDesign.from_json(design_json)
        except Exception as exc:
            raise AdminError(f"Invalid design: {exc}") from exc
        return await asyncio.to_thread(self._writer.save, design, overwrite=overwrite)

    @guard
    async def read_raw_template(self, name: str) -> str:
        return await asyncio.to_thread(self._app.scenario_mgr.read_compose_template, name)

    @guard
    async def save_raw_template(self, name: str, text: str) -> None:
        await asyncio.to_thread(
            self._app.scenario_mgr.save_scenario_files,
            name,
            text,
            None,
            None,
            overwrite=True,
        )

    # -- modules ------------------------------------------------------------

    @guard
    async def list_modules(self) -> list[ModuleRow]:
        def _collect() -> list[ModuleRow]:
            modules = self._app.module_mgr.list_modules()
            references = self._app.module_mgr.reference_count(
                None, self._app.prj_mgr, self._app.enroll_mgr
            )
            return [
                ModuleRow(name=name, path=str(path), references=references.get(name, 0))
                for name, path in sorted(modules.items())
            ]

        return await asyncio.to_thread(_collect)

    @guard
    async def create_module(self, name: str) -> None:
        name = required(name, "Module name")
        await asyncio.to_thread(self._app.module_mgr.create_module, name)

    @guard
    async def build_module(self, name: str) -> tuple[bool, str]:
        code, text = await self._app.module_mgr.build_module_text(name)
        return code == 0, text or "(no build output)"

    @guard
    async def remove_module(self, name: str) -> None:
        await self._app.module_mgr.remove_module(name, self._app.prj_mgr, self._app.enroll_mgr)

    def _module_file(self, name: str, file_name: str) -> Path:
        module_dir = self._app.module_mgr.get_path(name).resolve()
        target = (module_dir / file_name).resolve()
        if module_dir != target and module_dir not in target.parents:
            raise AdminError(f"Invalid module file name {file_name!r}.")
        return target

    @guard
    async def list_module_files(self, name: str) -> list[str]:
        def _collect() -> list[str]:
            module_dir = self._app.module_mgr.get_path(name)
            return sorted(
                str(path.relative_to(module_dir))
                for path in module_dir.rglob("*")
                if path.is_file()
            )

        return await asyncio.to_thread(_collect)

    @guard
    async def read_module_file(self, name: str, file_name: str) -> str:
        def _read() -> str:
            target = self._module_file(name, file_name)
            if not target.is_file():
                raise AdminError(f"Module `{name}` has no file `{file_name}`.")
            return target.read_text(encoding="utf-8", errors="replace")

        return await asyncio.to_thread(_read)

    @guard
    async def save_module_file(self, name: str, file_name: str, text: str) -> None:
        def _write() -> None:
            target = self._module_file(name, file_name)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")

        await asyncio.to_thread(_write)

    # -- progress -----------------------------------------------------------

    @guard
    async def leaderboard(self, project_name: str) -> list[LeaderboardRow]:
        def _collect() -> list[LeaderboardRow]:
            project = self._app.prj_mgr.get_project(project_name)
            items = self._app.enroll_mgr.get_leaderboard(project)
            return [
                LeaderboardRow(
                    position=position,
                    username=item["user"],
                    found_secrets=item["found_secrets"],
                    total_secrets=item["total_secrets"],
                    last_submit=_format_time(item["last_submit_time"]),
                )
                for position, item in enumerate(items, start=1)
            ]

        return await asyncio.to_thread(_collect)

    def _progress(self, username: str, project_name: str):
        user = self._app.user_mgr.get_user(username)
        project = self._app.prj_mgr.get_project(project_name)
        return self._app.enroll_mgr.get_enrollment(user, project).progress

    @guard
    async def solved_secrets(self, username: str, project_name: str) -> list[SolvedSecretRow]:
        def _collect() -> list[SolvedSecretRow]:
            progress = self._progress(username, project_name)
            rows = [
                SolvedSecretRow(
                    scenario=record.scenario_name,
                    name=record.local_name,
                    submitted_at=_format_time(record.submitted_at),
                    cluster_kind=str(record.cluster_kind),
                )
                for record in progress.solved_secrets.values()
            ]
            rows.sort(key=lambda row: row.submitted_at)
            return rows

        return await asyncio.to_thread(_collect)

    @guard
    async def submission_log(self, username: str, project_name: str) -> list[SubmissionRow]:
        def _collect() -> list[SubmissionRow]:
            progress = self._progress(username, project_name)
            return [
                SubmissionRow(value=entry.value, timestamp=_format_time(entry.timestamp))
                for entry in progress.submission_log
            ]

        return await asyncio.to_thread(_collect)

    # -- logs ---------------------------------------------------------------

    @guard
    async def project_cluster_logs(self, project_name: str, tail: int = 500) -> str:
        cluster = await asyncio.to_thread(self._project_cluster, project_name)
        return await self._app.project_cluster_mgr.compose_logs_text(cluster, tail=tail)

    @guard
    async def user_cluster_logs(self, username: str, project_name: str, tail: int = 500) -> str:
        cluster = await asyncio.to_thread(self._user_cluster, username, project_name)
        return await self._app.user_cluster_mgr.compose_logs_text(cluster, tail=tail)

    # -- sessions -----------------------------------------------------------

    @guard
    async def user_sessions(self, username: str) -> list[SessionRow]:
        def _collect() -> list[SessionRow]:
            user = self._app.user_mgr.get_user(username)
            rows = [
                SessionRow(
                    username=username,
                    kind="rendezvous",
                    state=str(getattr(session.state, "value", session.state)),
                    timestamp=_format_time(session.timestamp),
                    detail="",
                )
                for session in user.sessions
            ]
            for project in self._app.enroll_mgr.get_enrolled_projects(username):
                enrollment = self._app.enroll_mgr.get_enrollment(user, project)
                rows.extend(
                    SessionRow(
                        username=username,
                        kind="instance",
                        state=str(getattr(session.state, "value", session.state)),
                        timestamp=_format_time(session.timestamp),
                        detail=project.name,
                    )
                    for session in enrollment.progress.sessions
                )
            rows.sort(key=lambda row: row.timestamp)
            return rows

        return await asyncio.to_thread(_collect)

    @guard
    async def project_sessions(self, project_name: str) -> list[SessionRow]:
        def _collect() -> list[SessionRow]:
            project = self._app.prj_mgr.get_project(project_name)
            rows: list[SessionRow] = []
            for user in self._app.enroll_mgr.get_enrollments_for_project(project):
                enrollment = self._app.enroll_mgr.get_enrollment(user, project)
                rows.extend(
                    SessionRow(
                        username=user.username,
                        kind="instance",
                        state=str(getattr(session.state, "value", session.state)),
                        timestamp=_format_time(session.timestamp),
                        detail=project_name,
                    )
                    for session in enrollment.progress.sessions
                )
                rows.extend(
                    SessionRow(
                        username=user.username,
                        kind="rendezvous",
                        state=str(getattr(session.state, "value", session.state)),
                        timestamp=_format_time(session.timestamp),
                        detail="",
                    )
                    for session in user.sessions
                )
            rows.sort(key=lambda row: row.timestamp)
            return rows

        return await asyncio.to_thread(_collect)

    @guard
    async def ssh_activity(
        self, username: str, project_name: str, tail: int = 2000
    ) -> list[SessionRow]:
        cluster = await asyncio.to_thread(self._user_cluster, username, project_name)
        text = await self._app.user_cluster_mgr.compose_logs_text(cluster, tail=tail)
        return parse_ssh_activity(username, text)
