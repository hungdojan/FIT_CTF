import re

import pytest

from fit_ctf_models.project import ProjectManager
from fit_ctf_utils.exceptions import (
    ProjectExistsException,
    ProjectNamingFormatException,
    ProjectNotExistException,
)

from tests import FixtureData


def test_create_project(empty_data: FixtureData):
    """Create a project."""
    ctf_mgr, _ = empty_data
    prj_mgr = ctf_mgr.prj_mgr

    data = {
        "name": "demo_project1",
        "max_nof_users": 5,
        "starting_port_bind": -1,
        "description": "",
    }
    assert not (ctf_mgr._paths["projects"] / data["name"]).is_dir()
    project = prj_mgr.init_project(**data)

    assert project
    assert (ctf_mgr._paths["projects"] / data["name"]).is_dir()
    assert (ctf_mgr._paths["projects"] / data["name"] / "users").is_dir()
    assert (ctf_mgr._paths["projects"] / data["name"] / "logs").is_dir()
    assert len(list(project.services.keys())) > 0


def test_creating_project_errors(
    empty_data: FixtureData,
):
    """Test errors during project initializations."""
    ctf_mgr, _ = empty_data

    prj_mgr = ctf_mgr.prj_mgr

    invalid_names = ["-dash-symbols", "UpperCaseName", "space in the name"]
    for name in invalid_names:
        with pytest.raises(ProjectNamingFormatException):
            prj_mgr.init_project(name=name, max_nof_users=5)

    # valid data
    data = {
        "name": "demo_project1",
        "max_nof_users": 5,
    }
    prj = prj_mgr.init_project(**data)
    assert prj

    with pytest.raises(ProjectExistsException):
        prj_mgr.init_project(name=data["name"], max_nof_users=5)


def test_get_projects(project_data: FixtureData):
    ctf_mgr, _ = project_data
    prj_mgr = ctf_mgr.prj_mgr
    prjs = ctf_mgr.prj_mgr.get_docs()

    assert len(list(ctf_mgr._paths["projects"].iterdir())) == len(prjs)

    projects = prj_mgr.get_projects_raw()
    assert len(projects) == len(prjs)
    assert set([p["name"] for p in projects]) == set([p.name for p in prjs])

    with pytest.raises(ProjectNotExistException):
        prj_mgr.get_project("bad_project")

    prj = prj_mgr.get_project("prj1")
    assert prj.name == "prj1"
    assert prj.active


def test_get_reserved_ports(
    project_data: FixtureData,
):
    ctf_mgr, _ = project_data
    prj_mgr = ctf_mgr.prj_mgr

    reserved_ports = prj_mgr.get_reserved_ports()
    for data in reserved_ports:
        prj = prj_mgr.get_doc_by_filter(name=data["name"])
        assert prj
        assert (prj.starting_port_bind == data["min_port"]) and (
            prj.starting_port_bind + prj.max_nof_users - 1 == data["max_port"]
        )


def test_disable_and_flush_project(connected_data: FixtureData):
    ctf_mgr, _ = connected_data
    prj_mgr = ctf_mgr.prj_mgr
    prjs = prj_mgr.get_docs()

    deleted_prj = prjs.pop(0)
    enrolled_users = ctf_mgr.user_enrollment_mgr.get_user_enrollments_for_project(
        deleted_prj
    )

    with pytest.raises(ProjectExistsException):
        prj_mgr.flush_project(deleted_prj)

    assert len(enrolled_users) == 2
    enrolled_count = len(
        ctf_mgr.user_enrollment_mgr.get_enrolled_projects(enrolled_users[0])
    )

    prj_mgr.disable_project(deleted_prj)

    assert not prj_mgr.get_project(deleted_prj.name, active=None).active
    new_enrollment_count = len(
        ctf_mgr.user_enrollment_mgr.get_enrolled_projects(enrolled_users[0])
    )

    assert new_enrollment_count < enrolled_count
    assert (ctf_mgr._paths["projects"] / deleted_prj.name).is_dir()

    prj_mgr.flush_project(deleted_prj)
    with pytest.raises(ProjectNotExistException):
        prj_mgr.get_project(deleted_prj.name)

    assert not (ctf_mgr._paths["projects"] / deleted_prj.name).exists()


def test_delete_project(
    project_data: FixtureData,
):
    ctf_mgr, _ = project_data
    prj_mgr = ctf_mgr.prj_mgr
    prjs = prj_mgr.get_docs()

    deleted_prj = prjs.pop(0)
    assert (ctf_mgr._paths["projects"] / deleted_prj.name).is_dir()

    # does nothing
    prj_mgr.delete_project("non_existing_project")

    prj_mgr.delete_project(deleted_prj.name)

    assert not (ctf_mgr._paths["projects"] / deleted_prj.name).is_dir()
    assert len(prj_mgr.get_docs()) == 1

    assert not prj_mgr.get_doc_by_id(deleted_prj.id)


def test_generate_port_forwarding_script(
    connected_data: FixtureData,
):
    ctf_mgr, tmp_path = connected_data
    prj_mgr = ctf_mgr.prj_mgr
    prjs = prj_mgr.get_docs()

    script_path = (tmp_path / "script.sh").resolve()
    ip_addr = "127.0.0.1"

    prj_mgr.generate_port_forwarding_script(prjs[0].name, ip_addr, str(script_path))

    assert script_path.is_file()
    with open(script_path, "r") as f:
        lines = [line.rstrip() for line in f]
        assert lines.pop(0) == "#!/usr/bin/env bash"
        assert not lines.pop(0)
        for _ in range(
            len(ctf_mgr.user_enrollment_mgr.get_user_enrollments_for_project(prjs[0]))
        ):
            assert re.match(
                r"firewall-cmd\s+--zone=public\s+"
                r"--add-forward-port="
                rf"port=\d+:proto=tcp:toport=\d+:toaddr={ip_addr}",
                lines.pop(0),
            )
        assert lines.pop(0) == "firewall-cmd --zone=public --add-masquerade"


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
