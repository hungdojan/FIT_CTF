"""Typed row objects shared by the live and preview gateways.

The manager layer returns loosely-typed dicts (``UserInfoDict``,
``RawProjectDict``, raw aggregation results). The UI renders these frozen
dataclasses instead, so both gateway implementations expose one well-defined
shape and pages never index into raw dicts.
"""

from __future__ import annotations

from dataclasses import dataclass

from fit_ctf.components.types import (
    HealthCheckDict,
    ProjectPortListingDict,
    RawProjectDict,
    UserInfoDict,
)


@dataclass(frozen=True, slots=True)
class UserRow:
    username: str
    email: str
    role: str
    active: bool
    projects: tuple[str, ...]

    @classmethod
    def from_raw(cls, raw: UserInfoDict) -> "UserRow":
        return cls(
            username=raw["username"],
            email=raw["email"],
            role=raw["role"],
            active=raw["active"],
            projects=tuple(raw["projects"]),
        )


@dataclass(frozen=True, slots=True)
class ProjectRow:
    name: str
    max_nof_users: int
    active_users: int
    active: bool

    @classmethod
    def from_raw(cls, raw: RawProjectDict) -> "ProjectRow":
        return cls(
            name=raw["name"],
            max_nof_users=raw["max_nof_users"],
            active_users=raw["active_users"],
            active=raw["active"],
        )


@dataclass(frozen=True, slots=True)
class EnrollmentRow:
    username: str
    project: str
    role: str
    active: bool
    forwarded_port: int

    @classmethod
    def from_raw(cls, project_name: str, raw: dict) -> "EnrollmentRow":
        return cls(
            username=raw["username"],
            project=project_name,
            role=raw["role"],
            active=raw["active"],
            forwarded_port=raw["forwarded_port"],
        )


@dataclass(frozen=True, slots=True)
class PortRangeRow:
    project: str
    min_port: int
    max_port: int

    @classmethod
    def from_raw(cls, raw: ProjectPortListingDict) -> "PortRangeRow":
        return cls(project=raw["name"], min_port=raw["min_port"], max_port=raw["max_port"])


@dataclass(frozen=True, slots=True)
class ClusterRow:
    kind: str  # "project" | "user"
    project: str
    username: str | None
    name: str  # cluster name, or "" when the cluster document is missing
    running: bool
    scenarios: tuple[str, ...]

    @property
    def exists(self) -> bool:
        return bool(self.name)


@dataclass(frozen=True, slots=True)
class ScenarioSummary:
    name: str
    user_cluster_count: int


@dataclass(frozen=True, slots=True)
class ModuleRow:
    name: str
    path: str
    references: int


@dataclass(frozen=True, slots=True)
class HealthRow:
    name: str
    image: str
    state: str

    @classmethod
    def from_raw(cls, raw: HealthCheckDict) -> "HealthRow":
        return cls(name=raw["name"], image=raw["image"], state=raw["state"])


@dataclass(frozen=True, slots=True)
class LeaderboardRow:
    position: int
    username: str
    found_secrets: int
    total_secrets: int
    last_submit: str  # formatted local time, "" when never submitted

    @property
    def percentage(self) -> str:
        if self.total_secrets <= 0:
            return "0.00 %"
        return f"{self.found_secrets / self.total_secrets * 100:.2f} %"


@dataclass(frozen=True, slots=True)
class SolvedSecretRow:
    scenario: str
    name: str
    submitted_at: str
    cluster_kind: str


@dataclass(frozen=True, slots=True)
class SubmissionRow:
    value: str
    timestamp: str


@dataclass(frozen=True, slots=True)
class SessionRow:
    username: str
    kind: str  # "rendezvous" | "instance" | "ssh"
    state: str
    timestamp: str
    detail: str
