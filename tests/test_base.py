from pathlib import Path

import pytest
from bson import ObjectId

from fit_ctf_backend.ctf_manager import CTFManager
from fit_ctf_backend.exceptions import ModuleNotExistsException
from fit_ctf_db_models.project import Project
from fit_ctf_db_models.user import User


def test_user(unconnected_data: tuple[CTFManager, Path, list[Project], list[User]]):
    ctf_mgr, _, _, usrs = unconnected_data
    user_mgr = ctf_mgr.user_mgr

    assert not user_mgr.get_doc_by_id(ObjectId())
    for u in usrs:
        user = user_mgr.get_doc_by_id(u.id)
        assert user and user.username == u.username

    assert not user_mgr.get_doc_by_id_raw(ObjectId())
    for u in usrs:
        user = user_mgr.get_doc_by_id_raw(u.id)
        assert user and user["username"] == u.username


def test_project(unconnected_data: tuple[CTFManager, Path, list[Project], list[User]]):
    ctf_mgr, _, prjs, _ = unconnected_data
    prj_mgr = ctf_mgr.prj_mgr

    assert not prj_mgr.get_doc_by_id_raw(ObjectId())
    prj = prj_mgr.get_doc_by_id_raw(prjs[0].id)
    assert prj and prj["name"] == prjs[0].name

    prj = prjs[0]

    assert Path(prj.compose_filepath).exists()

    with pytest.raises(ModuleNotExistsException):
        prj.get_user_module("random_module")

    with pytest.raises(ModuleNotExistsException):
        prj.get_project_module("random_module")


def test_user_config(
    connected_data: tuple[CTFManager, Path, list[Project], list[User]],
):
    ctf_mgr, _, prjs, usrs = connected_data
    user_config_mgr = ctf_mgr.user_config_mgr

    assert not user_config_mgr.get_doc_by_id_raw(ObjectId())
    uc = user_config_mgr.get_user_config(prjs[0], usrs[1])
    search_uc = user_config_mgr.get_doc_by_id_raw(uc.id)
    assert (
        search_uc
        and search_uc["user_id"].id == uc.user_id.id
        and search_uc["project_id"].id == uc.project_id.id
    )


def test_base(unconnected_data: tuple[CTFManager, Path, list[Project], list[User]]):
    ctf_mgr, _, prjs, usrs = unconnected_data
    prj_mgr = ctf_mgr.prj_mgr
    user_mgr = ctf_mgr.user_mgr

    assert len(user_mgr.get_users()) == 3
    assert not user_mgr.remove_doc_by_id(ObjectId())
    u = usrs.pop(0)
    assert user_mgr.remove_doc_by_id(u.id)
    assert len(user_mgr.get_users()) == 2

    assert not user_mgr.remove_doc_by_filter(username="not_a_user")
    assert user_mgr.remove_doc_by_filter(username=usrs[0].username)
    assert len(user_mgr.get_users()) == 1

    assert prj_mgr.remove_docs_by_id([ObjectId(), ObjectId()]) == 0
    assert prj_mgr.remove_docs_by_id([p.id for p in prjs]) == len(prjs)
    assert len(prj_mgr.get_projects()) == 0
