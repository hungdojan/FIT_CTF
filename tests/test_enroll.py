from __future__ import annotations

from pathlib import Path

import pytest

from fit_ctf_backend.ctf_manager import CTFManager
from fit_ctf_backend.exceptions import (
    MaxUserCountReachedException,
    PortUsageCollisionException,
    ProjectNotExistException,
    UserNotEnrolledToProjectException,
    UserNotExistsException,
)
from fit_ctf_db_models.project import Project
from fit_ctf_db_models.user import User


def test_user_is_enrolled_to_the_project(
    connected_data: tuple[CTFManager, Path, list[Project], list[User]]
):
    ctf_mgr, _, prjs, usrs = connected_data
    user_config_mgr = ctf_mgr.user_config_mgr

    # fill mgr with data
    assert not user_config_mgr.user_is_enrolled_to_the_project(prjs[0], usrs[0])
    assert not user_config_mgr.user_is_enrolled_to_the_project(prjs[1], usrs[2])

    assert user_config_mgr.user_is_enrolled_to_the_project(prjs[0], usrs[1])
    assert user_config_mgr.user_is_enrolled_to_the_project(prjs[0], usrs[2])
    assert user_config_mgr.user_is_enrolled_to_the_project(prjs[1], usrs[0])
    assert user_config_mgr.user_is_enrolled_to_the_project(prjs[1], usrs[1])


def test_get_user_config(
    connected_data: tuple[CTFManager, Path, list[Project], list[User]]
):
    ctf_mgr, _, prjs, usrs = connected_data
    user_config_mgr = ctf_mgr.user_config_mgr

    with pytest.raises(UserNotEnrolledToProjectException):
        user_config_mgr.get_user_config(prjs[0], usrs[0])

    uc = user_config_mgr.get_user_config(prjs[0], usrs[1])
    assert uc.active and uc.user_id.id == usrs[1].id and uc.project_id.id == prjs[0].id


def test_enroll_user_to_project(
    connected_data: tuple[CTFManager, Path, list[Project], list[User]],
):
    ctf_mgr, tmp_path, prjs, usrs = connected_data
    user_config_mgr = ctf_mgr.user_config_mgr
    prj_mgr = ctf_mgr.prj_mgr
    user_mgr = ctf_mgr.user_mgr

    with pytest.raises(UserNotExistsException):
        user_config_mgr.enroll_user_to_project("user", "prj")

    with pytest.raises(ProjectNotExistException):
        user_config_mgr.enroll_user_to_project(usrs[0].username, "project")

    stored_uc = user_config_mgr.get_user_config(prjs[0], usrs[1])
    uc = user_config_mgr.enroll_user_to_project(usrs[1].username, prjs[0].name)
    assert stored_uc.id == uc.id

    with pytest.raises(PortUsageCollisionException):
        user_config_mgr.enroll_user_to_project(
            usrs[0].username, prjs[0].name, ssh_port=stored_uc.ssh_port
        )

    with pytest.raises(PortUsageCollisionException):
        user_config_mgr.enroll_user_to_project(
            usrs[0].username, prjs[0].name, forwarded_port=stored_uc.forwarded_port
        )

    mount_path = Path(prjs[0].config_root_dir) / prjs[0].volume_mount_dirname
    assert not (mount_path / usrs[0].username).is_dir()

    uc = user_config_mgr.enroll_user_to_project(usrs[0].username, prjs[0].name)
    assert uc.user_id.id == usrs[0].id and uc.project_id.id == prjs[0].id
    assert len(prj_mgr.get_active_users_for_project(prjs[0])) == prjs[0].max_nof_users
    assert (mount_path / usrs[0].username).is_dir()
    assert user_config_mgr.get_doc_by_id(uc.id) is not None

    user, _ = user_mgr.create_new_user(
        "newUser", "StrongPassw0rd", str((tmp_path / "shadow").resolve())
    )

    with pytest.raises(MaxUserCountReachedException):
        user_config_mgr.enroll_user_to_project(user.username, prjs[0].name)
