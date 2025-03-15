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


class ProjectPortListing(TypedDict):
    id: str
    name: str
    min_port: int
    max_port: int


class RawEnrolledProjects(TypedDict):
    name: str
    active: bool
    max_nof_users: int
    active_users: int


class HealthCheckDict(TypedDict):
    name: str
    image: str
    state: str


class ModuleCount(TypedDict):
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
