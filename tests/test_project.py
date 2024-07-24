import json
import re
import zipfile
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
from fit_ctf_db_models.project import Project, ProjectManager
from fit_ctf_db_models.user import User

# empty data

# def test_(empty_data: tuple[CTFManager, Path, list[Project], list[User]]):
#     """Create a project."""
#     ctf_mgr, tmp_path, _, _ = empty_data
#     prj_mgr = ctf_mgr.prj_mgr


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


# project_data

# def test_
#     project_data: tuple[CTFManager, Path, list[Project], list[User]]
# ):
#     ctf_mgr, _, prjs, _ = project_data
#     prj_mgr = ctf_mgr.prj_mgr


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


def test_get_reserved_ports(
    project_data: tuple[CTFManager, Path, list[Project], list[User]]
):
    ctf_mgr, _, prjs, _ = project_data
    prj_mgr = ctf_mgr.prj_mgr

    reserved_ports = prj_mgr.get_reserved_ports()
    for prj in prjs:
        for data in reserved_ports:
            if prj.name != data["name"]:
                continue
            assert (prj.starting_port_bind == data["min_port"]) and (
                prj.starting_port_bind + prj.max_nof_users == data["max_port"]
            )


def test_delete_project(
    project_data: tuple[CTFManager, Path, list[Project], list[User]]
):
    ctf_mgr, tmp_path, prjs, _ = project_data
    prj_mgr = ctf_mgr.prj_mgr

    deleted_prj = prjs.pop(0)
    assert (tmp_path / deleted_prj.name).is_dir()

    prj_mgr.delete_project("non_existing_project")
    prj_mgr.delete_project(deleted_prj.name)

    assert len(prj_mgr.get_projects()) == len(prjs)
    assert not (tmp_path / deleted_prj.name).is_dir()
    assert len(prj_mgr.get_docs(active=True)) == 1
    assert len(prj_mgr.get_docs()) == 2

    query_prj = prj_mgr.get_doc_by_id(deleted_prj.id)
    assert query_prj and not query_prj.active


def test_delete_all(project_data: tuple[CTFManager, Path, list[Project], list[User]]):
    ctf_mgr, tmp_path, prjs, _ = project_data
    prj_mgr = ctf_mgr.prj_mgr

    prj_mgr.delete_all()
    assert not any([(tmp_path / p.name).is_dir() for p in prjs])
    assert not prj_mgr.get_docs()


# connected_data

# def test_(
#     connected_data: tuple[CTFManager, Path, list[Project], list[User]]
# ):
#     ctf_mgr, tmp_path, prjs, usrs = connected_data
#     prj_mgr = ctf_mgr.prj_mgr


def test_get_active_users_for_project(
    connected_data: tuple[CTFManager, Path, list[Project], list[User]]
):
    ctf_mgr, _, prjs, usrs = connected_data
    prj_mgr = ctf_mgr.prj_mgr
    with pytest.raises(ProjectNotExistException):
        prj_mgr.get_active_users_for_project("random_project")

    assert len(prj_mgr.get_active_users_for_project(prjs[1])) == 2
    assert set(
        [u.username for u in prj_mgr.get_active_users_for_project(prjs[0])]
    ) == set([u.username for u in usrs[1:]])

    # raw data
    raw_data = prj_mgr.get_active_users_for_project_raw(prjs[0])
    assert len(raw_data) == 2
    assert set([d["mount"] for d in raw_data]) == set(
        [
            prjs[0].config_root_dir
            + "/"
            + prjs[0].volume_mount_dirname
            + "/"
            + d["username"]
            for d in raw_data
        ]
    )
    assert all([d.get("forwarded_port") for d in raw_data])
    assert set([d["username"] for d in raw_data]) == set([u.username for u in usrs[1:]])
    assert all(Path(d["mount"]).is_dir() for d in raw_data)

    raw_data = prj_mgr.get_active_users_for_project_raw(prjs[1].name)
    assert len(raw_data) == 2
    assert set([d["mount"] for d in raw_data]) == set(
        [
            prjs[1].config_root_dir
            + "/"
            + prjs[1].volume_mount_dirname
            + "/"
            + d["username"]
            for d in raw_data
        ]
    )
    assert all([d.get("forwarded_port") for d in raw_data])
    assert set([d["username"] for d in raw_data]) == set(
        [u.username for u in usrs[:-1]]
    )


def test_generate_port_forwarding_script(
    connected_data: tuple[CTFManager, Path, list[Project], list[User]]
):
    ctf_mgr, tmp_path, prjs, _ = connected_data
    prj_mgr = ctf_mgr.prj_mgr

    script_path = (tmp_path / "script.sh").resolve()
    ip_addr = "127.0.0.1"

    prj_mgr.generate_port_forwarding_script(prjs[0].name, ip_addr, str(script_path))

    assert script_path.is_file()
    with open(script_path, "r") as f:
        lines = [l.rstrip() for l in f]
        assert lines.pop(0) == "#!/usr/bin/env bash"
        assert not lines.pop(0)
        for _ in range(len(prj_mgr.get_active_users_for_project(prjs[0]))):
            assert re.match(
                r"firewall-cmd\s+--zone=public\s+"
                r"--add-forward-port="
                rf"port=\d+:proto=tcp:toport=\d+:toaddr={ip_addr}",
                lines.pop(0),
            )
        assert lines.pop(0) == "firewall-cmd --zone=public --add-masquerade"


def test_export_project(
    connected_data: tuple[CTFManager, Path, list[Project], list[User]]
):
    ctf_mgr, tmp_path, prjs, _ = connected_data
    prj_mgr = ctf_mgr.prj_mgr

    zip_path = (tmp_path / "archive.zip").resolve()
    prj_mgr.export_project(prjs[0].name, str(zip_path))
    assert zip_path.is_file()
    with zipfile.ZipFile(zip_path) as zf:
        files = zf.namelist()

        # pop enrolled user list
        enrolled_users_filepath = files.pop(0)
        f = zf.open(enrolled_users_filepath)

        data = json.load(f)
        assert len(data) == len(prj_mgr.get_active_users_for_project(prjs[0]))
        f.close()
        assert all([f.startswith(prjs[0].name) for f in files])

        # check archive content
        inside_prj_dir = [f.lstrip(f"{prjs[0].name}/") for f in files]
        assert "server_compose.yaml.j2" in inside_prj_dir
        assert "server_compose.yaml" in inside_prj_dir
        assert "user_compose.yaml.j2" in inside_prj_dir
        assert any([f.startswith("admin/") for f in inside_prj_dir])

    # test after compiling all users compose files

    # test after starting all user login nodes


# static methods


def test_validate_project_name():
    assert ProjectManager.validate_project_name("valid_name")
    assert ProjectManager.validate_project_name("valid_123")
    assert ProjectManager.validate_project_name("123val1d")

    assert not ProjectManager.validate_project_name("Invalid_name")
    assert not ProjectManager.validate_project_name("INVALID")
    assert not ProjectManager.validate_project_name("not-valid")
    assert not ProjectManager.validate_project_name("also not valid")
    assert not ProjectManager.validate_project_name("not_special_chars!!")


# Project tests
