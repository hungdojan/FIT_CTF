from enum import Enum
import pathlib
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
    _id: str
    name: str
    min_port: int
    max_port: int


class RawEnrolledProjects(TypedDict):
    name: str
    active: bool
    max_nof_users: int
    active_users: int
