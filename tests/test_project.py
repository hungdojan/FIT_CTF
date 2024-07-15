from pathlib import Path

import pytest

from fit_ctf_backend.ctf_manager import CTFManager
from fit_ctf_backend.exceptions import (
    DirNotEmptyException,
    DirNotExistsException,
    ProjectExistsException,
    ProjectNamingFormatException,
    ProjectNotExistException,
)
from fit_ctf_db_models.project import Project
from fit_ctf_db_models.user import User


# ProjectManager tests
def test_create_project(empty_data: tuple[CTFManager, Path, list[Project], list[User]]):
    """Create a project."""
    ctf_mgr, tmp_path, _, _ = empty_data

    prj_mgr = ctf_mgr.prj_mgr
    data = {
        "name": "demo_project1",
        "dest_dir": str(tmp_path.resolve()),
        "max_nof_users": 5,
        "starting_port_bind": -1,
        "volume_mount_dirname": "_mounts",
        "dir_name": "",
        "description": "",
        "compose_file": "server_compose.yaml",
    }
    assert not (tmp_path / data["name"]).is_dir()
    project = prj_mgr.init_project(**data)

    assert project
    assert (tmp_path / data["name"]).is_dir()
    assert (tmp_path / data["name"] / data["volume_mount_dirname"]).is_dir()
    assert (tmp_path / data["name"] / data["compose_file"]).is_file()
    assert (tmp_path / data["name"] / "admin").is_dir()
    assert (tmp_path / data["name"] / "_mounts").is_dir()
    assert not (tmp_path / data["name"] / "_modules").is_dir()


def test_creating_project_errors(
    empty_data: tuple[CTFManager, Path, list[Project], list[User]]
):
    """Test errors during project initializations."""
    ctf_mgr, tmp_path, _, _ = empty_data

    prj_mgr = ctf_mgr.prj_mgr

    with pytest.raises(ProjectNamingFormatException):
        prj_mgr.init_project(
            name="-dash-symbols", dest_dir=str(tmp_path.resolve()), max_nof_users=5
        )

    with pytest.raises(ProjectNamingFormatException):
        prj_mgr.init_project(
            name="UpperCaseName", dest_dir=str(tmp_path.resolve()), max_nof_users=5
        )

    with pytest.raises(ProjectNamingFormatException):
        prj_mgr.init_project(
            name="space in the name", dest_dir=str(tmp_path.resolve()), max_nof_users=5
        )

    with pytest.raises(ProjectNamingFormatException):
        prj_mgr.init_project(
            name="space in the name", dest_dir=str(tmp_path.resolve()), max_nof_users=5
        )

    # valid data
    data = {
        "name": "demo_project1",
        "dest_dir": str(tmp_path.resolve()),
        "max_nof_users": 5,
        "starting_port_bind": -1,
        "volume_mount_dirname": "_mounts",
        "dir_name": "",
        "description": "",
        "compose_file": "server_compose.yaml",
    }
    prj = prj_mgr.init_project(**data)
    assert prj

    with pytest.raises(ProjectExistsException):
        prj_mgr.init_project(
            name=data["name"], dest_dir=str(tmp_path.resolve()), max_nof_users=5
        )

    with pytest.raises(DirNotExistsException):
        prj_mgr.init_project(
            name="valid_name",
            dest_dir=str(
                (tmp_path / "a-random-directory-that-does-not-exist").resolve()
            ),
            max_nof_users=5,
        )
    new_dst = tmp_path / "prj2"
    new_dst.mkdir()
    (new_dst / "file").touch()

    with pytest.raises(DirNotEmptyException):
        prj_mgr.init_project(
            name="prj2",
            dest_dir=str(tmp_path.resolve()),
            max_nof_users=5,
        )

    (new_dst / "file").unlink()
    prj = prj_mgr.init_project(
        name="prj2",
        dest_dir=str(tmp_path.resolve()),
        max_nof_users=5,
    )
    assert prj


def test_get_projects(project_data: tuple[CTFManager, Path, list[Project], list[User]]):
    ctf_mgr, _, prjs, _ = project_data

    projects = ctf_mgr.prj_mgr.get_projects()
    assert len(projects) == len(prjs)
    assert set([p["name"] for p in projects]) == set([p.name for p in prjs])

    with pytest.raises(ProjectNotExistException):
        ctf_mgr.prj_mgr.get_project("bad_project")

    prj = ctf_mgr.prj_mgr.get_project("prj1")
    assert prj is not None
    assert prj.name == "prj1"
    assert prj.active


# Project tests
