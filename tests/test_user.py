from pathlib import Path

import pytest

from fit_ctf_backend.ctf_manager import CTFManager
from fit_ctf_backend.exceptions import DirNotExistsException, UserExistsException, UserNotExistsException
from fit_ctf_db_models.project import Project
from fit_ctf_db_models.user import User, UserManager


# empty data
def test_empty_mgr(empty_data: tuple[CTFManager, Path, list[Project], list[User]]):
    ctf_mgr, _, _, _ = empty_data
    user_mgr = ctf_mgr.user_mgr
    assert len(user_mgr.get_users()) == 0

def test_create_user(
    empty_data: tuple[CTFManager, Path, list[Project], list[User]]
):
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
        user_mgr.create_new_user("user2", "user2Password", str((tmp_path / "not_exist")))




# user data
def test_get_user(user_data: tuple[CTFManager, Path, list[Project], list[User]]):
    ctf_mgr, _, _, usrs = user_data
    user_mgr = ctf_mgr.user_mgr

    with pytest.raises(UserNotExistsException):
        user_mgr.get_user("nope")

    assert all([user_mgr.get_user(u.username) for u in usrs])


def test_validate_user_login(
    user_data: tuple[CTFManager, Path, list[Project], list[User]]
):
    ctf_mgr, _, _, _ = user_data
    user_mgr = ctf_mgr.user_mgr
    assert not user_mgr.validate_user_login("nope", "what")

    assert not user_mgr.validate_user_login("user1", "user1")
    assert user_mgr.validate_user_login("user1", "user1Password")


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
