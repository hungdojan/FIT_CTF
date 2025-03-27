import pathlib
from enum import Enum
from typing import TypedDict


class UserRole(str, Enum):
    """Enumeration of user roles."""

    USER = "user"
    ADMIN = "admin"


class PathDict(TypedDict):
    projects: pathlib.Path
    users: pathlib.Path
    modules: pathlib.Path


class ProjectPortListingDict(TypedDict):
    id: str
    name: str
    min_port: int
    max_port: int


class RawEnrolledProjectsDict(TypedDict):
    name: str
    active: bool
    max_nof_users: int
    active_users: int


class HealthCheckDict(TypedDict):
    name: str
    image: str
    state: str


class ModuleCountDict(TypedDict):
    _id: str
    count: int


class DatabaseDumpDict(TypedDict):
    project: dict
    users: list
    modules: list
    enrollments: list


class SetupDict(TypedDict):
    projects: list
    users: list
    enrollments: list
    options: dict


class RawProjectDict(TypedDict):
    name: str
    max_nof_users: int
    active_users: int
    active: bool


class UserInfoDict(TypedDict):
    username: str
    email: str
    role: str
    active: bool
    projects: list[str]


class NewUserDict(TypedDict):
    username: str
    password: str
