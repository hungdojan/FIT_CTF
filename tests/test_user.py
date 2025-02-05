import re
from pathlib import Path
from typing import Callable

import pytest

from fit_ctf_backend.ctf_manager import CTFManager
from fit_ctf_backend.exceptions import (
    DirNotExistsException,
    UserExistsException,
    UserNotExistsException,
)
from fit_ctf_db_models.project import Project
from fit_ctf_db_models.user import User, UserManager


# empty data
def test_empty_mgr(empty_data: tuple[CTFManager, Path, list[Project], list[User]]):
    ctf_mgr, _, _, _ = empty_data
    user_mgr = ctf_mgr.user_mgr
    assert len(user_mgr.get_users()) == 0


def test_create_user(empty_data: tuple[CTFManager, Path, list[Project], list[User]]):
    ctf_mgr, tmp_path, _, _ = empty_data
    user_mgr = ctf_mgr.user_mgr

    assert len(user_mgr.get_users()) == 0
    user_path = (tmp_path / "shadow").resolve()

    user, data = user_mgr.create_new_user("user1", "user1Password", str(user_path))
    assert len(user_mgr.get_users()) == 1
    assert Path(user.shadow_path).is_file()
    assert data["username"] == "user1"
    assert data["password"] == "user1Password"

    with pytest.raises(UserExistsException):
        user_mgr.create_new_user("user1", "user1Password", str(user_path))

    with pytest.raises(DirNotExistsException):
        user_mgr.create_new_user(
            "user2", "user2Password", str((tmp_path / "not_exist"))
        )


def test_create_multiple_users(
    empty_data: tuple[CTFManager, Path, list[Project], list[User]],
):
    ctf_mgr, tmp_path, _, _ = empty_data
    user_mgr = ctf_mgr.user_mgr
    shadow_dir = tmp_path / "shadow"

    assert len(user_mgr.get_users()) == 0

    lof_users = [f"user{i+1}" for i in range(5)] + ["user2", "user3"]
    len_lu = len(set(lof_users))
    data = user_mgr.create_multiple_users(lof_users, str(shadow_dir.resolve()))

    assert len(user_mgr.get_users()) == len_lu
    for username, password in data.items():
        assert user_mgr.validate_user_login(username, password)
        assert (shadow_dir / username).is_file()

    lof_users = [f"User{i+1}" for i in range(2)]
    default_password = "TheDefaultPassw0rd"
    data = user_mgr.create_multiple_users(
        lof_users, str(shadow_dir.resolve()), default_password
    )

    assert len(user_mgr.get_users()) == len_lu + len(set(lof_users))
    for username in data.keys():
        assert user_mgr.validate_user_login(username, default_password)
        assert (shadow_dir / username).is_file()


# user data
def test_get_users(user_data: tuple[CTFManager, Path, list[Project], list[User]]):
    ctf_mgr, _, _, usrs = user_data
    user_mgr = ctf_mgr.user_mgr

    with pytest.raises(UserNotExistsException):
        user_mgr.get_user("nope")

    assert len([user_mgr.get_user(u.username) for u in usrs]) == len(
        user_mgr.get_users()
    )
    assert len(user_mgr.get_users()) == len(usrs)
    assert set([u.username for u in usrs]) == set(
        [u["username"] for u in user_mgr.get_users()]
    )


def test_validate_user_login(
    user_data: tuple[CTFManager, Path, list[Project], list[User]],
):
    ctf_mgr, _, _, _ = user_data
    user_mgr = ctf_mgr.user_mgr
    assert not user_mgr.validate_user_login("nope", "what")

    assert not user_mgr.validate_user_login("user1", "user1")
    assert user_mgr.validate_user_login("user1", "user1Password")


def test_get_password_hash(
    user_data: tuple[CTFManager, Path, list[Project], list[User]],
):
    ctf_mgr, _, _, usrs = user_data
    user_mgr = ctf_mgr.user_mgr

    assert not usrs[0].password == user_mgr.get_password_hash("wrong_password")
    assert usrs[0].password == user_mgr.get_password_hash(f"{usrs[0].username}Password")


def test_change_password(user_data: tuple[CTFManager, Path, list[Project], list[User]]):
    def check_shadow_hash(path: Path, comp: Callable[[str], bool]):
        assert path.is_file()
        with open(path, "r") as f:
            for line in f:
                if line.startswith("user:"):
                    res = re.match(r"user:([^:]+):.*", line)
                    assert res
                    assert comp(res.group(1))

    ctf_mgr, _, _, usrs = user_data
    user_mgr = ctf_mgr.user_mgr

    assert user_mgr.validate_user_login(usrs[0].username, f"{usrs[0].username}Password")
    shadow_path = Path(usrs[0].shadow_path)
    old_shadow_hash = usrs[0].shadow_hash
    check_shadow_hash(shadow_path, (lambda x: x == old_shadow_hash))

    user_mgr.change_password(usrs[0].username, f"{usrs[0].username}NewPassword")
    assert not user_mgr.validate_user_login(
        usrs[0].username, f"{usrs[0].username}Password"
    )
    assert user_mgr.validate_user_login(
        usrs[0].username, f"{usrs[0].username}NewPassword"
    )

    check_shadow_hash(shadow_path, (lambda x: x != old_shadow_hash))


# connected_data
def test_get_active_projects_for_user(
    connected_data: tuple[CTFManager, Path, list[Project], list[User]],
):
    ctf_mgr, _, _, usrs = connected_data
    user_mgr = ctf_mgr.user_mgr
    expected_data = {"user1": {"prj2"}, "user2": {"prj1", "prj2"}, "user3": {"prj1"}}
    for u in usrs:
        data = expected_data[u.username]
        prj_data = set(
            [p.name for p in user_mgr.get_active_projects_for_user(u.username)]
        )
        assert data == prj_data


def test_delete_a_user(
    connected_data: tuple[CTFManager, Path, list[Project], list[User]],
):
    ctf_mgr, _, _, _ = connected_data
    user_mgr = ctf_mgr.user_mgr
    expected_data = {"user1": {}, "user2": {"prj1", "prj2"}, "user3": {"prj1"}}

    user_mgr.delete_a_user("user1")
    for u in user_mgr.get_docs():
        assert (not u.active and len(expected_data[u.username]) == 0) or (
            u.active and len(expected_data[u.username]) > 0
        )

    assert len(ctf_mgr.prj_mgr.get_active_users_for_project("prj1")) == 2
    assert len(ctf_mgr.prj_mgr.get_active_users_for_project("prj2")) == 1


def test_delete_users(
    connected_data: tuple[CTFManager, Path, list[Project], list[User]],
):
    ctf_mgr, _, _, _ = connected_data
    user_mgr = ctf_mgr.user_mgr
    prj_mgr = ctf_mgr.prj_mgr
    expected_data = {"prj1": {"user3"}, "prj2": set()}

    user_mgr.delete_users(["user1", "user2"])
    assert len(user_mgr.get_users()) == 1
    assert len(user_mgr.get_users(True)) == 3

    for p, us in expected_data.items():
        assert set([u.username for u in prj_mgr.get_active_users_for_project(p)]) == us


def test_get_active_projects_for_user_raw(
    connected_data: tuple[CTFManager, Path, list[Project], list[User]],
):
    ctf_mgr, _, _, _ = connected_data
    user_mgr = ctf_mgr.user_mgr

    prjs = user_mgr.get_active_projects_for_user_raw("user2")
    for prj in prjs:
        assert all(
            k in prj for k in {"name", "active", "max_nof_users", "active_users"}
        )
        assert prj["active"]
        assert prj["active_users"] == 2


# static methods


def test_validate_password_strength():
    assert not UserManager.validate_password_strength("short")
    assert not UserManager.validate_password_strength("very long password")
    assert not UserManager.validate_password_strength("very long password with digit 1")
    assert not UserManager.validate_password_strength(
        "very long password with upper case U"
    )
    assert not UserManager.validate_password_strength("Sh0rt")

    assert UserManager.validate_password_strength("ValidPassw0rd")


def test_generate_password():
    with pytest.raises(ValueError):
        UserManager.generate_password(-1)

    assert UserManager.generate_password(0) == ""
    assert len(UserManager.generate_password(10)) == 10
    assert len(UserManager.generate_password(8)) == 8


def test_validate_username_format():
    assert not UserManager.validate_username_format("gg")
    assert not UserManager.validate_username_format("invalid-name")
    assert not UserManager.validate_username_format("space space")
    assert not UserManager.validate_username_format("spec. characters!")
    assert not UserManager.validate_username_format("under_score")

    assert UserManager.validate_username_format("ssss")
    assert UserManager.validate_username_format("numbers1")
