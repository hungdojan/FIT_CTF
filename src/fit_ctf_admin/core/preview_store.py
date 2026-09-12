"""In-memory sample data backing preview mode.

Preview mode lets the whole TUI run and be tested without MongoDB or a
container runtime. The store mirrors the semantics the managers enforce
(duplicates, capacity, missing entities) closely enough for realistic demos.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field

from fit_ctf.components.types import UserRole
from fit_ctf.models.infra.utils import (
    validate_secrets_vs_templates,
    validate_service_configs_vs_scaffold,
)
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
from fit_ctf_admin.scenario.compose_export import export_compose_preview
from fit_ctf_admin.scenario.design_model import (
    FALLBACK_MODULE_NAMES,
    ScenarioDesign,
)
from fit_ctf_admin.scenario.draft import (
    draft_to_config,
    normalize_draft,
    scaffold_draft,
)
from fit_ctf_admin.scenario.secret_macro import expand_secret_macros

_DEFAULT_STARTING_PORT = 10_000


@dataclass
class _UserRecord:
    username: str
    email: str = ""
    role: str = UserRole.USER.value
    active: bool = True
    password: str = ""


@dataclass
class _ProjectRecord:
    name: str
    max_nof_users: int
    starting_port: int
    active: bool = True
    description: str = ""


@dataclass
class _EnrollmentRecord:
    username: str
    project: str
    role: str
    forwarded_port: int
    active: bool = True


@dataclass
class PreviewStore:
    users: list[_UserRecord] = field(default_factory=list)
    projects: list[_ProjectRecord] = field(default_factory=list)
    enrollments: list[_EnrollmentRecord] = field(default_factory=list)
    # cluster running flags: project name / (username, project name)
    project_clusters_running: dict[str, bool] = field(default_factory=dict)
    user_clusters_running: dict[tuple[str, str], bool] = field(default_factory=dict)
    # scenario template definitions: name -> {"secret_keys", "scaffold", "config_params"}
    scenario_defs: dict[str, dict] = field(default_factory=dict)
    # assigned scenario configs (canonical draft dicts) per cluster
    project_scenario_configs: dict[str, dict[str, dict]] = field(default_factory=dict)
    user_scenario_configs: dict[tuple[str, str], dict[str, dict]] = field(default_factory=dict)
    # designer storage: scenario name -> {"design_json": str | None, "compose_text": str}
    designs: dict[str, dict] = field(default_factory=dict)
    # module registry: name -> reference count
    modules: dict[str, int] = field(
        default_factory=lambda: {name: 0 for name in FALLBACK_MODULE_NAMES}
    )
    # module files: (module name, relative file name) -> content
    module_files: dict[tuple[str, str], str] = field(default_factory=dict)
    # progress / logs / sessions sample data
    progress: dict[str, list[dict]] = field(default_factory=dict)
    solved: dict[tuple[str, str], list[dict]] = field(default_factory=dict)
    submissions: dict[tuple[str, str], list[dict]] = field(default_factory=dict)
    logs: dict[str, str] = field(default_factory=dict)
    sessions: list[dict] = field(default_factory=list)
    _next_port: int = _DEFAULT_STARTING_PORT

    @classmethod
    def with_sample_data(cls) -> "PreviewStore":
        store = cls()
        store.users = [
            _UserRecord("alice", "alice@fit.cvut.cz"),
            _UserRecord("bob", "bob@fit.cvut.cz", role=UserRole.ADMIN.value),
            _UserRecord("carol", active=False),
            _UserRecord("dave", "dave@example.com"),
        ]
        store.projects = [
            _ProjectRecord("intro_linux", 50, 10_000),
            _ProjectRecord("web_exploitation", 30, 11_000),
            _ProjectRecord("archived_2024", 10, 12_000, active=False),
        ]
        store.enrollments = [
            _EnrollmentRecord("alice", "intro_linux", UserRole.USER.value, 10_000),
            _EnrollmentRecord("alice", "web_exploitation", UserRole.USER.value, 11_000),
            _EnrollmentRecord("bob", "intro_linux", UserRole.ADMIN.value, 10_001),
            _EnrollmentRecord("dave", "web_exploitation", UserRole.USER.value, 11_001),
        ]
        store.project_clusters_running = {
            "intro_linux": True,
            "web_exploitation": False,
        }
        store.user_clusters_running = {("alice", "intro_linux"): True}
        store.modules = {"template": 0, "ssh_debian": 0, "ssh_ubi": 4}
        store.module_files = {
            (name, "Containerfile"): (
                f"FROM registry.example/base:latest\n# module {name} (preview sample)\n"
                'COPY entrypoint.sh /entrypoint.sh\nENTRYPOINT ["/entrypoint.sh"]\n'
            )
            for name in store.modules
        } | {(name, "entrypoint.sh"): "#!/bin/sh\nexec sleep infinity\n" for name in store.modules}
        store.progress = {
            "intro_linux": [
                {
                    "username": "alice",
                    "found": 3,
                    "total": 5,
                    "last_submit": "2026-09-05 14:02:11",
                },
                {
                    "username": "bob",
                    "found": 5,
                    "total": 5,
                    "last_submit": "2026-09-04 21:47:03",
                },
            ],
            "web_exploitation": [
                {
                    "username": "alice",
                    "found": 1,
                    "total": 4,
                    "last_submit": "2026-09-03 10:12:45",
                },
                {"username": "dave", "found": 0, "total": 4, "last_submit": ""},
            ],
        }
        store.solved = {
            ("alice", "intro_linux"): [
                {
                    "scenario": "web_stack",
                    "name": "flag_web",
                    "submitted_at": "2026-09-05 14:02:11",
                    "cluster_kind": "user",
                },
            ],
        }
        store.submissions = {
            ("alice", "intro_linux"): [
                {"value": "FLAG{wrong}", "timestamp": "2026-09-05 13:58:02"},
                {"value": "FLAG{demo}", "timestamp": "2026-09-05 14:02:11"},
            ],
        }
        store.logs = {
            "project:intro_linux": (
                "intro_linux_admin | admin node ready\n"
                "intro_linux_admin | serving on 0.0.0.0:8000\n"
            ),
            "user:alice@intro_linux": (
                "login_node | Server listening on 0.0.0.0 port 22.\n"
                "login_node | Accepted password for alice from 10.89.0.7 port 51322 ssh2\n"
                "login_node | pam_unix(sshd:session): session opened for user alice\n"
                "login_node | pam_unix(sshd:session): session closed for user alice\n"
            ),
        }
        store.sessions = [
            {
                "username": "alice",
                "kind": "rendezvous",
                "state": "LOGIN",
                "timestamp": "2026-09-05 13:40:00",
                "detail": "",
            },
            {
                "username": "alice",
                "kind": "instance",
                "state": "START",
                "timestamp": "2026-09-05 13:41:12",
                "detail": "intro_linux",
            },
            {
                "username": "alice",
                "kind": "rendezvous",
                "state": "LOGOUT",
                "timestamp": "2026-09-05 14:20:31",
                "detail": "",
            },
            {
                "username": "bob",
                "kind": "rendezvous",
                "state": "LOGIN",
                "timestamp": "2026-09-04 21:30:00",
                "detail": "",
            },
        ]
        store.scenario_defs = {
            "login_node": {"secret_keys": [], "scaffold": {}, "config_params": []},
            "admin_node": {"secret_keys": [], "scaffold": {}, "config_params": []},
            "web_stack": {
                "secret_keys": ["flag_web"],
                "scaffold": {
                    "web": {
                        "env_map": {"ADMIN": ""},
                        "port_map": {"http": ""},
                        "volume_map": {},
                    }
                },
                "config_params": [],
            },
        }
        empty_cfg = {"secrets": {}, "service_configs": {}, "config_params": {}}
        web_cfg = {
            "secrets": {"flag_web": "FLAG{demo}"},
            "service_configs": {
                "web": {
                    "env_map": {"ADMIN": "admin"},
                    "port_map": {"http": 8080},
                    "volume_map": {},
                }
            },
            "config_params": {},
        }
        store.project_scenario_configs = {
            "intro_linux": {"admin_node": copy.deepcopy(empty_cfg)},
            "web_exploitation": {
                "admin_node": copy.deepcopy(empty_cfg),
                "web_stack": web_cfg,
            },
        }
        store.user_scenario_configs = {
            (e.username, e.project): {"login_node": copy.deepcopy(empty_cfg)}
            for e in store.enrollments
        }
        store._next_port = 13_000
        return store

    # -- lookups ----------------------------------------------------------

    def _user(self, username: str) -> _UserRecord:
        user = next((u for u in self.users if u.username == username), None)
        if user is None:
            raise AdminError(f"User `{username}` was not found.")
        return user

    def _project(self, name: str) -> _ProjectRecord:
        project = next((p for p in self.projects if p.name == name), None)
        if project is None:
            raise AdminError(f"Project `{name}` was not found.")
        return project

    def _user_projects(self, username: str) -> tuple[str, ...]:
        return tuple(
            sorted(e.project for e in self.enrollments if e.username == username and e.active)
        )

    def _active_count(self, project_name: str) -> int:
        return sum(1 for e in self.enrollments if e.project == project_name and e.active)

    # -- users ------------------------------------------------------------

    def user_row(self, record: _UserRecord) -> UserRow:
        return UserRow(
            username=record.username,
            email=record.email,
            role=record.role,
            active=record.active,
            projects=self._user_projects(record.username),
        )

    def list_users(self, include_inactive: bool = False) -> list[UserRow]:
        records = self.users if include_inactive else [u for u in self.users if u.active]
        return [self.user_row(record) for record in records]

    def create_user(
        self,
        username: str,
        password: str,
        email: str = "",
        role: UserRole = UserRole.USER,
    ) -> UserRow:
        if any(u.username == username for u in self.users):
            raise AdminError(f"User `{username}` already exists.")
        record = _UserRecord(username, email=email, role=role.value, password=password)
        self.users.append(record)
        return self.user_row(record)

    def change_password(self, username: str, password: str) -> None:
        self._user(username).password = password

    def update_user(self, username: str, email: str, role: UserRole) -> UserRow:
        record = self._user(username)
        record.email = email
        record.role = role.value
        return self.user_row(record)

    def disable_user(self, username: str) -> None:
        user = self._user(username)
        user.active = False
        for enrollment in self.enrollments:
            if enrollment.username == username:
                enrollment.active = False

    def delete_user(self, username: str) -> None:
        # idempotent like ``UserManager.delete_users``: missing users are skipped
        self.users = [u for u in self.users if u.username != username]
        self.enrollments = [e for e in self.enrollments if e.username != username]

    # -- projects ---------------------------------------------------------

    def project_row(self, record: _ProjectRecord) -> ProjectRow:
        return ProjectRow(
            name=record.name,
            max_nof_users=record.max_nof_users,
            active_users=self._active_count(record.name),
            active=record.active,
        )

    def list_projects(self, include_inactive: bool = False) -> list[ProjectRow]:
        records = self.projects if include_inactive else [p for p in self.projects if p.active]
        return [self.project_row(record) for record in records]

    def create_project(
        self,
        name: str,
        max_nof_users: int,
        starting_port_bind: int = -1,
        description: str = "",
    ) -> ProjectRow:
        if any(p.name == name for p in self.projects):
            raise AdminError(f"Project `{name}` already exists.")
        start_port = starting_port_bind if starting_port_bind >= 0 else self._next_port
        self._next_port = max(self._next_port, start_port + max_nof_users)
        record = _ProjectRecord(name, max_nof_users, start_port, description=description)
        self.projects.append(record)
        return self.project_row(record)

    def disable_project(self, name: str) -> None:
        project = self._project(name)
        project.active = False
        for enrollment in self.enrollments:
            if enrollment.project == name:
                enrollment.active = False

    def delete_project(self, name: str) -> None:
        # idempotent like ``ProjectManager.delete_project``: missing projects are skipped
        self.projects = [p for p in self.projects if p.name != name]
        self.enrollments = [e for e in self.enrollments if e.project != name]

    def reserved_ports(self) -> list[PortRangeRow]:
        return [
            PortRangeRow(
                project=p.name,
                min_port=p.starting_port,
                max_port=p.starting_port + p.max_nof_users,
            )
            for p in self.projects
            if p.active
        ]

    # -- enrollments ------------------------------------------------------

    @staticmethod
    def enrollment_row(record: _EnrollmentRecord) -> EnrollmentRow:
        return EnrollmentRow(
            username=record.username,
            project=record.project,
            role=record.role,
            active=record.active,
            forwarded_port=record.forwarded_port,
        )

    def list_enrollments(
        self, project_name: str, include_inactive: bool = False
    ) -> list[EnrollmentRow]:
        self._project(project_name)
        records = [
            e
            for e in self.enrollments
            if e.project == project_name and (include_inactive or e.active)
        ]
        records.sort(key=lambda e: e.username)
        return [self.enrollment_row(record) for record in records]

    def list_all_enrollments(self, include_inactive: bool = False) -> list[EnrollmentRow]:
        records = [e for e in self.enrollments if include_inactive or e.active]
        records.sort(key=lambda e: (e.project, e.username))
        return [self.enrollment_row(record) for record in records]

    def enrollable_users(self, project_name: str) -> list[str]:
        self._project(project_name)
        enrolled = {e.username for e in self.enrollments if e.project == project_name and e.active}
        return sorted(u.username for u in self.users if u.active and u.username not in enrolled)

    def enroll_user(self, username: str, project_name: str) -> EnrollmentRow:
        user = self._user(username)
        project = self._project(project_name)
        if not user.active or not project.active:
            raise AdminError("Inactive users or projects cannot be enrolled.")
        if any(
            e.username == username and e.project == project_name and e.active
            for e in self.enrollments
        ):
            raise AdminError(f"User `{username}` is already enrolled in `{project_name}`.")
        active_count = self._active_count(project_name)
        if active_count >= project.max_nof_users:
            raise AdminError(f"Project `{project_name}` is at capacity.")
        record = _EnrollmentRecord(
            username, project_name, user.role, project.starting_port + active_count
        )
        self.enrollments.append(record)
        return self.enrollment_row(record)

    def cancel_enrollment(self, username: str, project_name: str) -> None:
        matched = False
        for enrollment in self.enrollments:
            if enrollment.username == username and enrollment.project == project_name:
                enrollment.active = False
                matched = True
        if not matched:
            raise AdminError(f"User `{username}` is not enrolled in `{project_name}`.")
        self.user_clusters_running.pop((username, project_name), None)

    # -- clusters -----------------------------------------------------------

    def list_project_clusters(self) -> list[ClusterRow]:
        return [
            ClusterRow(
                kind="project",
                project=p.name,
                username=None,
                name=f"{p.name}_project_cluster",
                running=self.project_clusters_running.get(p.name, False),
                scenarios=tuple(self.project_scenario_configs.get(p.name, {})),
            )
            for p in self.projects
            if p.active
        ]

    def list_user_clusters(self, project_name: str) -> list[ClusterRow]:
        self._project(project_name)
        records = sorted(
            (e for e in self.enrollments if e.project == project_name and e.active),
            key=lambda e: e.username,
        )
        return [
            ClusterRow(
                kind="user",
                project=project_name,
                username=e.username,
                name=f"{project_name}_{e.username}",
                running=self.user_clusters_running.get((e.username, project_name), False),
                scenarios=tuple(self.user_scenario_configs.get((e.username, project_name), {})),
            )
            for e in records
        ]

    def set_project_cluster_running(self, project_name: str, running: bool) -> None:
        self._project(project_name)
        self.project_clusters_running[project_name] = running

    def set_user_cluster_running(self, username: str, project_name: str, running: bool) -> None:
        if not any(
            e.username == username and e.project == project_name and e.active
            for e in self.enrollments
        ):
            raise AdminError(f"User `{username}` is not enrolled in `{project_name}`.")
        self.user_clusters_running[(username, project_name)] = running

    def project_cluster_health(self, project_name: str) -> list[HealthRow]:
        self._project(project_name)
        running = self.project_clusters_running.get(project_name, False)
        state = "running" if running else "exited"
        return [
            HealthRow(
                name=f"{project_name}_{scenario}",
                image=f"fit-ctf/{scenario}",
                state=state,
            )
            for scenario in self.project_scenario_configs.get(project_name, {"admin_node": {}})
        ]

    def user_cluster_health(self, username: str, project_name: str) -> list[HealthRow]:
        running = self.user_clusters_running.get((username, project_name), False)
        state = "running" if running else "exited"
        return [
            HealthRow(
                name=f"{project_name}_{username}_{scenario}",
                image=f"fit-ctf/{scenario}",
                state=state,
            )
            for scenario in self.user_scenario_configs.get(
                (username, project_name), {"login_node": {}}
            )
        ]

    def stop_all_user_clusters(self, project_name: str) -> None:
        self._project(project_name)
        for key in list(self.user_clusters_running):
            if key[1] == project_name:
                self.user_clusters_running[key] = False

    # -- scenarios ----------------------------------------------------------

    def _scenario_def(self, name: str) -> dict:
        definition = self.scenario_defs.get(name)
        if definition is None:
            raise AdminError(f"Scenario `{name}` does not exist.")
        return definition

    def _assigned_configs(self, kind: str, project_name: str, username: str | None) -> dict:
        self._project(project_name)
        if kind == "project":
            return self.project_scenario_configs.setdefault(project_name, {})
        if kind == "user":
            if not username:
                raise AdminError("Select a user for the user cluster target.")
            self._user(username)
            return self.user_scenario_configs.setdefault((username, project_name), {})
        raise AdminError(f"Unknown cluster kind {kind!r}.")

    def list_scenarios(self) -> list[ScenarioSummary]:
        counts: dict[str, int] = {name: 0 for name in self.scenario_defs}
        for configs in self.user_scenario_configs.values():
            for name in configs:
                counts[name] = counts.get(name, 0) + 1
        return [
            ScenarioSummary(name=name, user_cluster_count=counts.get(name, 0))
            for name in sorted(self.scenario_defs)
        ]

    def create_scenario(self, name: str) -> None:
        name = name.strip()
        if not re.fullmatch(r"[a-z0-9_]+", name):
            raise AdminError(
                f"Invalid scenario name {name!r}: use lowercase letters, digits, "
                "and underscores only."
            )
        if name in self.scenario_defs:
            raise AdminError(f"Scenario `{name}` already exists.")
        self.scenario_defs[name] = {
            "secret_keys": [],
            "scaffold": {},
            "config_params": [],
        }

    def delete_scenario(self, name: str) -> None:
        self._scenario_def(name)
        user_usage = sum(1 for cfg in self.user_scenario_configs.values() if name in cfg)
        project_usage = sum(1 for cfg in self.project_scenario_configs.values() if name in cfg)
        if user_usage or project_usage:
            raise AdminError(
                f"Scenario `{name}` is assigned to {user_usage} user cluster(s) and "
                f"{project_usage} project cluster(s). Unassign it first."
            )
        del self.scenario_defs[name]

    def assigned_scenarios(self, kind: str, project_name: str, username: str | None) -> list[str]:
        return sorted(self._assigned_configs(kind, project_name, username).keys())

    def scenario_config_draft(
        self, kind: str, project_name: str, username: str | None, scenario: str
    ) -> dict:
        definition = self._scenario_def(scenario)
        configs = self._assigned_configs(kind, project_name, username)
        existing = configs.get(scenario)
        if existing is not None:
            return copy.deepcopy(existing)
        return scaffold_draft(
            list(definition["secret_keys"]),
            copy.deepcopy(definition["scaffold"]),
            set(definition["config_params"]),
        )

    def validate_scenario_config(self, scenario: str, raw: dict) -> tuple[list[str], list[str]]:
        definition = self._scenario_def(scenario)
        normalized, errors = normalize_draft(raw)
        if errors:
            return errors, []
        config = draft_to_config(scenario, normalized)
        secret_errors, secret_warnings = validate_secrets_vs_templates(
            frozenset(definition["secret_keys"]), config.secrets
        )
        service_errors, service_warnings = validate_service_configs_vs_scaffold(
            copy.deepcopy(definition["scaffold"]), config.service_configs
        )
        return secret_errors + service_errors, secret_warnings + service_warnings

    def apply_scenario_config(
        self,
        kind: str,
        project_name: str,
        username: str | None,
        scenario: str,
        raw: dict,
    ) -> list[str]:
        errors, warnings = self.validate_scenario_config(scenario, raw)
        if errors:
            raise AdminError("Fix the config first: " + "; ".join(errors))
        normalized, _ = normalize_draft(raw)
        # <gen> macros expand at apply time, like the live gateway
        normalized["secrets"] = expand_secret_macros(normalized["secrets"])
        self._assigned_configs(kind, project_name, username)[scenario] = normalized
        return warnings

    def compile_scenario(
        self, kind: str, project_name: str, username: str | None, scenario: str
    ) -> list[str]:
        configs = self._assigned_configs(kind, project_name, username)
        if scenario not in configs:
            raise AdminError(f"Scenario `{scenario}` is not assigned to this cluster.")
        _, warnings = self.validate_scenario_config(scenario, configs[scenario])
        return warnings

    def unassign_scenario(
        self, kind: str, project_name: str, username: str | None, scenario: str
    ) -> None:
        configs = self._assigned_configs(kind, project_name, username)
        if scenario not in configs:
            raise AdminError(f"Scenario `{scenario}` is not assigned to this cluster.")
        del configs[scenario]

    # -- designer -----------------------------------------------------------

    def designer_state(self, name: str) -> str:
        stored = self.designs.get(name)
        if stored is not None and stored["design_json"] is not None:
            return "ours"
        if name in self.scenario_defs:
            return "foreign"
        return "new"

    def designer_load(self, name: str) -> tuple[str | None, str, str]:
        stored = self.designs.get(name)
        if stored is not None and stored["design_json"] is not None:
            return stored["design_json"], stored["compose_text"], "sidecar"
        if stored is not None:
            return None, stored["compose_text"], "raw"
        if name in self.scenario_defs:
            return (
                None,
                f"# scenario `{name}` (no designer data in preview mode)\n",
                "raw",
            )
        raise AdminError(f"Scenario `{name}` does not exist.")

    def designer_save(self, design_json: str, *, overwrite: bool = False) -> list[str]:
        try:
            design = ScenarioDesign.from_json(design_json)
        except Exception as exc:
            raise AdminError(f"Invalid design: {exc}") from exc
        if not design.blocks:
            raise AdminError("Add at least one service before saving the scenario.")
        network_errors = design.invalid_networks()
        if network_errors:
            raise AdminError("; ".join(network_errors))
        if not re.fullmatch(r"[a-z0-9_]+", design.name):
            raise AdminError(
                f"Invalid scenario name {design.name!r}: use lowercase letters, "
                "digits, and underscores only."
            )
        if design.name in self.scenario_defs and not overwrite:
            raise AdminError(f"Scenario `{design.name}` already exists.")
        compose_text = export_compose_preview(design)
        self.designs[design.name] = {
            "design_json": design.to_json(),
            "compose_text": compose_text,
        }
        # register the template definition so assignment works on the design
        self.scenario_defs[design.name] = {
            "secret_keys": list(design.secrets),
            "scaffold": {
                block.service_key: {
                    "env_map": {key: "" for key in block.env_keys},
                    "port_map": {key: "" for key in block.ports},
                    "volume_map": {slot.name: {"src_path": ""} for slot in block.volumes},
                }
                for block in design.blocks
            },
            "config_params": [],
        }
        return []

    def read_raw_template(self, name: str) -> str:
        _, compose_text, _ = self.designer_load(name)
        return compose_text

    def save_raw_template(self, name: str, text: str) -> None:
        if name not in self.scenario_defs:
            self.scenario_defs[name] = {
                "secret_keys": [],
                "scaffold": {},
                "config_params": [],
            }
        # raw edits invalidate any stored design (hash mismatch in live mode)
        self.designs.pop(name, None)
        self.designs[name] = {"design_json": None, "compose_text": text}

    # -- modules ------------------------------------------------------------

    def list_modules(self) -> list[ModuleRow]:
        return [
            ModuleRow(name=name, path=f"(preview)/modules/{name}", references=refs)
            for name, refs in sorted(self.modules.items())
        ]

    def create_module(self, name: str) -> None:
        name = name.strip()
        if not name:
            raise AdminError("Module name is required.")
        if name in self.modules:
            raise AdminError(f"Module `{name}` already exists.")
        self.modules[name] = 0
        self.module_files[(name, "Containerfile")] = (
            "FROM registry.example/base:latest\n# new module (preview)\n"
        )
        self.module_files[(name, "entrypoint.sh")] = "#!/bin/sh\nexec sleep infinity\n"

    def remove_module(self, name: str) -> None:
        if name not in self.modules:
            raise AdminError(f"Module `{name}` was not found.")
        if self.modules[name] > 0:
            raise AdminError(f"Module `{name}` is still used by some services.")
        del self.modules[name]
        for key in [key for key in self.module_files if key[0] == name]:
            del self.module_files[key]

    # -- progress / logs / sessions ------------------------------------------

    def leaderboard(self, project_name: str) -> list[LeaderboardRow]:
        self._project(project_name)
        rows = [
            LeaderboardRow(
                position=0,
                username=entry["username"],
                found_secrets=entry["found"],
                total_secrets=entry["total"],
                last_submit=entry["last_submit"],
            )
            for entry in self.progress.get(project_name, [])
        ]
        rows.sort(key=lambda row: (-row.found_secrets, row.last_submit))
        return [
            LeaderboardRow(
                position=index,
                username=row.username,
                found_secrets=row.found_secrets,
                total_secrets=row.total_secrets,
                last_submit=row.last_submit,
            )
            for index, row in enumerate(rows, start=1)
        ]

    def solved_secrets(self, username: str, project_name: str) -> list[SolvedSecretRow]:
        self._project(project_name)
        self._user(username)
        return [SolvedSecretRow(**raw) for raw in self.solved.get((username, project_name), [])]

    def submission_log(self, username: str, project_name: str) -> list[SubmissionRow]:
        self._project(project_name)
        self._user(username)
        return [SubmissionRow(**raw) for raw in self.submissions.get((username, project_name), [])]

    def cluster_logs(self, key: str) -> str:
        return self.logs.get(key, f"# no logs recorded for {key} (preview mode)\n")

    def session_rows(self, username: str | None, project_name: str | None) -> list[SessionRow]:
        rows = [SessionRow(**raw) for raw in self.sessions]
        if username is not None:
            rows = [row for row in rows if row.username == username]
        if project_name is not None:
            enrolled = {e.username for e in self.enrollments if e.project == project_name}
            rows = [
                row
                for row in rows
                if row.username in enrolled
                and (row.kind == "rendezvous" or row.detail in ("", project_name))
            ]
        rows.sort(key=lambda row: row.timestamp)
        return rows

    def list_module_files(self, name: str) -> list[str]:
        if name not in self.modules:
            raise AdminError(f"Module `{name}` was not found.")
        return sorted(file for module, file in self.module_files if module == name)

    def read_module_file(self, name: str, file_name: str) -> str:
        try:
            return self.module_files[(name, file_name)]
        except KeyError:
            raise AdminError(f"Module `{name}` has no file `{file_name}`.") from None

    def save_module_file(self, name: str, file_name: str, text: str) -> None:
        if name not in self.modules:
            raise AdminError(f"Module `{name}` was not found.")
        self.module_files[(name, file_name)] = text
