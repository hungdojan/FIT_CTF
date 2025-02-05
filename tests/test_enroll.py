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


def _get_mount_path(project: Project, user: User) -> Path:
    return Path(project.config_root_dir) / project.volume_mount_dirname / user.username


def _get_compose_file_path(project: Project, username: str) -> Path:
    return Path(project.config_root_dir) / f"{username}_compose.yaml"


def test_user_is_enrolled_to_the_project(
    connected_data: tuple[CTFManager, Path, list[Project], list[User]],
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
    connected_data: tuple[CTFManager, Path, list[Project], list[User]],
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


def test_enroll_multiple_users_to_project(
    unconnected_data: tuple[CTFManager, Path, list[Project], list[User]],
):
    ctf_mgr, tmp_path, prjs, _ = unconnected_data
    user_config_mgr = ctf_mgr.user_config_mgr
    prj_mgr = ctf_mgr.prj_mgr
    user_mgr = ctf_mgr.user_mgr

    new_usernames = ["user4", "user5"]
    user_mgr.create_multiple_users(
        new_usernames, str((tmp_path / "shadow").resolve()), "userPassw0rd"
    )
    new_users = user_mgr.get_docs(username={"$in": new_usernames}, active=True)

    with pytest.raises(MaxUserCountReachedException):
        user_config_mgr.enroll_multiple_users_to_project(
            [f"user{i+1}" for i in range(5)], prjs[0].name
        )

    assert len(prj_mgr.get_active_users_for_project(prjs[0].name)) == 0
    ucs = user_config_mgr.enroll_multiple_users_to_project(new_usernames, prjs[0].name)
    assert len(ucs) == len(new_usernames)
    assert len(ucs) == len(prj_mgr.get_active_users_for_project(prjs[0].name))

    assert set([uc.user_id.id for uc in ucs]) == set([u.id for u in new_users])
    ucs = user_config_mgr.enroll_multiple_users_to_project(
        [f"user{i+3}" for i in range(3)], prjs[0].name
    )

    assert len(ucs) == 1
    assert set([u.user_id.id for u in ucs]).difference(set([u.id for u in new_users]))


def test_get_user_info(
    connected_data: tuple[CTFManager, Path, list[Project], list[User]],
):
    ctf_mgr, _, prjs, usrs = connected_data
    user_config_mgr = ctf_mgr.user_config_mgr

    res = user_config_mgr.get_user_info(usrs[1])
    assert all([i["active"] for i in res])
    assert set([i.name for i in prjs]) == set([i["name"] for i in res])


def test_cancel_user_enrollment(
    connected_data: tuple[CTFManager, Path, list[Project], list[User]],
):
    ctf_mgr, _, prjs, usrs = connected_data
    user_config_mgr = ctf_mgr.user_config_mgr
    prj_mgr = ctf_mgr.prj_mgr

    with pytest.raises(UserNotEnrolledToProjectException):
        user_config_mgr.cancel_user_enrollment(usrs[0].username, prjs[0].name)

    assert len(prj_mgr.get_active_users_for_project(prjs[0])) == 2

    uc = user_config_mgr.get_user_config(prjs[0], usrs[1])
    assert uc and uc.active
    assert _get_mount_path(prjs[0], usrs[1]).is_dir()
    compose_file = Path(prjs[0].config_root_dir) / f"{usrs[1].username}_compose.yaml"
    assert compose_file.is_file()

    user_config_mgr.cancel_user_enrollment(usrs[1].username, prjs[0].name)

    old_uc = user_config_mgr.get_doc_by_filter(
        **{"user_id.$id": usrs[1].id, "project_id.$id": prjs[0].id}
    )
    assert old_uc and not old_uc.active
    assert not _get_mount_path(prjs[0], usrs[1]).exists()
    assert not compose_file.is_file()

    assert len(prj_mgr.get_active_users_for_project(prjs[0])) == 1
    with pytest.raises(UserNotEnrolledToProjectException):
        user_config_mgr.cancel_user_enrollment(usrs[1].username, prjs[0].name)


def test_cancel_multiple_enrollments(
    connected_data: tuple[CTFManager, Path, list[Project], list[User]],
):
    ctf_mgr, _, prjs, usrs = connected_data
    user_config_mgr = ctf_mgr.user_config_mgr
    prj_mgr = ctf_mgr.prj_mgr

    with pytest.raises(UserNotEnrolledToProjectException):
        user_config_mgr.cancel_user_enrollment(usrs[0].username, prjs[0].name)

    docs = prj_mgr.get_active_users_for_project_raw(prjs[0])
    assert all([doc["active"] for doc in docs])
    assert len(docs) == 2
    assert all([Path(doc["mount"]).is_dir() for doc in docs])
    compose_files = [_get_compose_file_path(prjs[0], doc["username"]) for doc in docs]
    assert all([cf.exists() for cf in compose_files])

    user_config_mgr.cancel_multiple_enrollments(
        [doc["username"] for doc in docs], prjs[0].name
    )

    docs = prj_mgr.get_active_users_for_project_raw(prjs[0])
    assert len(docs) == 0

    docs = user_config_mgr.get_docs_raw({"project_id.$id": prjs[0].id}, {})
    assert len(docs) == 2
    assert (
        len(
            [
                i
                for i in (
                    Path(prjs[0].config_root_dir) / prjs[0].volume_mount_dirname
                ).glob("*")
            ]
        )
        == 0
    )
    assert not all([cf.exists() for cf in compose_files])

    docs = prj_mgr.get_active_users_for_project_raw(prjs[1])
    assert all([doc["active"] for doc in docs])
    assert len(docs) == 2
    assert all([Path(doc["mount"]).is_dir() for doc in docs])
    compose_files = [_get_compose_file_path(prjs[1], doc["username"]) for doc in docs]
    assert all([cf.exists() for cf in compose_files])

    user_config_mgr.cancel_multiple_enrollments([], prjs[1].name)

    docs = prj_mgr.get_active_users_for_project_raw(prjs[1])
    assert all([doc["active"] for doc in docs])
    assert len(docs) == 2
    assert all([Path(doc["mount"]).is_dir() for doc in docs])
    assert all([cf.exists() for cf in compose_files])


def test_cancel_all_project_enrollments(
    connected_data: tuple[CTFManager, Path, list[Project], list[User]],
):
    ctf_mgr, _, prjs, usrs = connected_data
    user_config_mgr = ctf_mgr.user_config_mgr
    user_mgr = ctf_mgr.user_mgr
    prj_mgr = ctf_mgr.prj_mgr

    # check user2 enrollments
    docs = prj_mgr.get_active_users_for_project_raw(prjs[0])
    assert len(docs) == 2
    assert all([Path(d["mount"]).is_dir() for d in docs])
    assert len(user_mgr.get_active_projects_for_user(usrs[1].username)) == 2
    compose_files = [_get_compose_file_path(prjs[0], doc["username"]) for doc in docs]
    assert all([cf.exists() for cf in compose_files])

    # remove all user enrollments from the project1
    user_config_mgr.cancel_all_project_enrollments(prjs[0])

    # check data after the enrollment cancellation
    assert len(prj_mgr.get_active_users_for_project(prjs[0])) == 0
    ucs = user_config_mgr.get_docs_raw({"project_id.$id": prjs[0].id}, {})
    assert len(ucs) == 2
    assert (
        len(
            [
                i
                for i in (
                    Path(prjs[0].config_root_dir) / prjs[0].volume_mount_dirname
                ).glob("*")
            ]
        )
        == 0
    )
    assert not all([cf.exists() for cf in compose_files])

    assert len(user_mgr.get_active_projects_for_user(usrs[1].username)) == 1


def test_cancel_user_enrollments_from_all_projects(
    connected_data: tuple[CTFManager, Path, list[Project], list[User]],
):
    ctf_mgr, _, _, usrs = connected_data
    user_config_mgr = ctf_mgr.user_config_mgr
    user_mgr = ctf_mgr.user_mgr

    # projects for user1
    prjs_user0 = user_mgr.get_active_projects_for_user(usrs[0].username)
    assert len(prjs_user0) == 1
    assert all([_get_mount_path(prj, usrs[0]).is_dir() for prj in prjs_user0])
    compose_files = [
        _get_compose_file_path(prj, usrs[0].username) for prj in prjs_user0
    ]
    assert all([cp.exists() for cp in compose_files])

    user_config_mgr.cancel_user_enrollments_from_all_projects(usrs[0].username)

    assert len(user_mgr.get_active_projects_for_user(usrs[0].username)) == 0
    assert not all([_get_mount_path(prj, usrs[0]).is_dir() for prj in prjs_user0])
    assert not all([cp.exists() for cp in compose_files])

    # projects for user2
    prjs_user1 = user_mgr.get_active_projects_for_user(usrs[1].username)
    assert len(prjs_user1) == 2
    assert all([_get_mount_path(prj, usrs[1]).is_dir() for prj in prjs_user1])
    compose_files = [
        _get_compose_file_path(prj, usrs[1].username) for prj in prjs_user0
    ]
    assert all([cp.exists() for cp in compose_files])

    user_config_mgr.cancel_user_enrollments_from_all_projects(usrs[1].username)

    assert len(user_mgr.get_active_projects_for_user(usrs[1].username)) == 0
    assert not all([_get_mount_path(prj, usrs[1]).is_dir() for prj in prjs_user1])
    assert not all([cp.exists() for cp in compose_files])
