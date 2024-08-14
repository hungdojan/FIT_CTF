
from __future__ import annotations

import os
from pathlib import Path

import pymongo.errors
import pytest
from _pytest.fixtures import FixtureRequest
from dotenv import load_dotenv

from fit_ctf_backend.ctf_manager import CTFManager
from fit_ctf_db_models.project import Project
from fit_ctf_db_models.user import User

load_dotenv()


@pytest.fixture
def empty_data(
    request: FixtureRequest,
    tmp_path: Path,
) -> tuple[CTFManager, Path, list[Project], list[User]]:
    """Yield an empty CTFManager object.

    :return: A CTFManager object, a path to the temporary directory,
    list of projects and users.
    :rtype: Iterator[tuple[CTFManager, Path, list[Project], list[User]]]
    """

    def teardown():
        # teardown ctf_mgr
        ctf_mgr.user_mgr.delete_all()
        ctf_mgr.prj_mgr.delete_all()
        ctf_mgr.user_config_mgr.clear_database()

    # get data
    db_host = os.getenv("DB_HOST")
    db_name = os.getenv("DB_TEST_NAME", "test-ctf-db")
    if not db_host:
        pytest.exit("DB_HOST environment variable is not set!")
    os.environ["LOG_DEST"] = str(tmp_path.resolve())


    # init testing env and clear database (just in case)
    try:
        ctf_mgr = CTFManager(db_host, db_name)
    except pymongo.errors.ServerSelectionTimeoutError:
        pytest.exit("DB is probably not running")

    ctf_mgr.prj_mgr.remove_docs_by_filter()
    ctf_mgr.user_mgr.remove_docs_by_filter()
    ctf_mgr.user_config_mgr.remove_docs_by_filter()

    # make a shadow dir
    (tmp_path / "shadow").mkdir()
    request.addfinalizer(teardown)
    return ctf_mgr, tmp_path, [], []


@pytest.fixture
def project_data(
    empty_data: tuple[CTFManager, Path, list[Project], list[User]]
) -> tuple[CTFManager, Path, list[Project], list[User]]:
    """Yield a CTFManager with 2 projects and destination directory.

    The manager contains following objects:
        Projects [enrolled]:
            - prj1 - []
            - prj2 - []

    :return: A CTFManager object, a path to the temporary directory,
    list of projects and users.
    :rtype: Iterator[tuple[CTFManager, Path, list[Project], list[User]]]
    """

    # init testing env
    ctf_mgr, tmp_path, prjs, usrs = empty_data
    prj_mgr = ctf_mgr.prj_mgr

    # fill mgr with data
    data = {
        "dest_dir": str(tmp_path.resolve()),
        "max_nof_users": 3,
    }
    prjs = [prj_mgr.init_project(name=f"prj{i+1}", **data) for i in range(2)]

    # yield data
    return ctf_mgr, tmp_path, prjs, usrs


@pytest.fixture
def user_data(
    empty_data: tuple[CTFManager, Path, list[Project], list[User]]
) -> tuple[CTFManager, Path, list[Project], list[User]]:
    """Yield a CTFManager with 3 users and destination directory.

    The manager contains following objects:
        Users [enrolled]:
            - user1 - []
            - user2 - []
            - user3 - []

    :return: A CTFManager object, a path to the temporary directory,
        list of projects and users.
    :rtype: Iterator[tuple[CTFManager, Path, list[Project], list[User]]]
    """
    # init testing env
    ctf_mgr, tmp_path, prjs, usrs = empty_data
    user_mgr = ctf_mgr.user_mgr

    # fill mgr with data
    usrs = [
        user_mgr.create_new_user(
            username=f"user{i+1}",
            password=f"user{i+1}Password",
            shadow_dir=str(tmp_path / "shadow"),
        )[0]
        for i in range(3)
    ]

    # yield data
    return ctf_mgr, tmp_path, prjs, usrs


@pytest.fixture
def unconnected_data(
    empty_data: tuple[CTFManager, Path, list[Project], list[User]]
) -> tuple[CTFManager, Path, list[Project], list[User]]:
    """Yield a CTFManager with 2 projects, 3 users, and destination directory.

    The manager contains following objects:
        Projects [enrolled]:
            - prj1 - []
            - prj2 - []
        Users [enrolled]:
            - user1 - []
            - user2 - []
            - user3 - []

    :return: A CTFManager object, a path to the temporary directory,
    list of projects and users.
    :rtype: Iterator[tuple[CTFManager, Path, list[Project], list[User]]]
    """
    # init testing env
    ctf_mgr, tmp_path, prjs, usrs = empty_data
    prj_mgr = ctf_mgr.prj_mgr
    user_mgr = ctf_mgr.user_mgr

    # fill mgr with data
    usrs = [
        user_mgr.create_new_user(
            username=f"user{i+1}",
            password=f"user{i+1}Password",
            shadow_dir=str(tmp_path / "shadow"),
        )[0]
        for i in range(3)
    ]

    data = {
        "dest_dir": str(tmp_path.resolve()),
        "max_nof_users": 3,
    }
    prjs = [prj_mgr.init_project(name=f"prj{i+1}", **data) for i in range(2)]

    # yield data
    return ctf_mgr, tmp_path, prjs, usrs


@pytest.fixture
def connected_data(
    unconnected_data: tuple[CTFManager, Path, list[Project], list[User]]
) -> tuple[CTFManager, Path, list[Project], list[User]]:
    """Yield a CTFManager with 2 projects, 3 users, and destination directory.

    The manager contains following objects:
        Projects [enrolled]:
            - prj1 - [user2, user3]
            - prj2 - [user1, user2]
        Users [enrolled]:
            - user1 - [prj2]
            - user2 - [prj1, prj2]
            - user3 - [prj1]

    :return: A CTFManager object, a path to the temporary directory,
    list of projects and users.
    :rtype: Iterator[tuple[CTFManager, Path, list[Project], list[User]]]
    """
    # init testing env
    ctf_mgr, tmp_path, prjs, usrs = unconnected_data
    user_config_mgr = ctf_mgr.user_config_mgr

    # fill mgr with data
    user_config_mgr.enroll_multiple_users_to_project(
        [u.username for u in usrs[1:]], prjs[0].name
    )
    user_config_mgr.enroll_multiple_users_to_project(
        [u.username for u in usrs[:-1]], prjs[1].name
    )

    [user_config_mgr.compile_compose(u, prjs[0]) for u in usrs[1:]]
    [user_config_mgr.compile_compose(u, prjs[1]) for u in usrs[:-1]]

    # yield data
    return ctf_mgr, tmp_path, prjs, usrs


@pytest.fixture
def modules_data(
    connected_data: tuple[CTFManager, Path, list[Project], list[User]]
) -> tuple[CTFManager, Path, list[Project], list[User]]:
    """Yield a CTFManager with 2 projects, 3 users, and destination directory.

    The manager contains following objects:
        Projects [enrolled] [modules]:
            - prj1 - [user2, user3] [prj1_prj_module1, prj1_prj_module2]
            - prj2 - [user1, user2] [prj2_prj_module1, prj2_prj_module2]
        Users [enrolled] [modules]:
            - user1 - [prj2]        [prj2_module1]
            - user2 - [prj1, prj2]  [prj2_module1, prj2_module2, prj1_module1]
            - user3 - [prj1]        [prj1_module1, prj1_module2]

    :return: A CTFManager object, a path to the temporary directory,
    list of projects and users.
    :rtype: Iterator[tuple[CTFManager, Path, list[Project], list[User]]]
    """
    # init testing env
    ctf_mgr, tmp_path, prjs, usrs = connected_data
    prj_mgr = ctf_mgr.prj_mgr
    user_mgr = ctf_mgr.user_mgr
    user_config_mgr = ctf_mgr.user_config_mgr

    # fill mgr with data
    for prj in prjs:
        for i in range(2):
            prj_mgr.create_project_module(prj.name, f"{prj.name}_prj_module{i+1}")
            prj_mgr.create_user_module(prj.name, f"{prj.name}_module{i+1}")

    usrs = user_mgr.get_docs()
    prjs = prj_mgr.get_docs()

    user_config_mgr.add_module(
        usrs[0], prjs[1], prjs[1].get_user_module(f"{prjs[1].name}_module1")
    )
    user_config_mgr.add_module(
        usrs[1], prjs[1], prjs[1].get_user_module(f"{prjs[1].name}_module1")
    )
    user_config_mgr.add_module(
        usrs[1], prjs[1], prjs[1].get_user_module(f"{prjs[1].name}_module2")
    )

    user_config_mgr.add_module(
        usrs[1], prjs[0], prjs[0].get_user_module(f"{prjs[0].name}_module1")
    )
    user_config_mgr.add_module(
        usrs[2], prjs[0], prjs[0].get_user_module(f"{prjs[0].name}_module1")
    )
    user_config_mgr.add_module(
        usrs[2], prjs[0], prjs[0].get_user_module(f"{prjs[0].name}_module2")
    )

    [user_config_mgr.compile_compose(u, prjs[0]) for u in usrs[1:]]
    [user_config_mgr.compile_compose(u, prjs[1]) for u in usrs[:-1]]

    # yield data
    return ctf_mgr, tmp_path, prjs, usrs


@pytest.fixture
def deleted_data(
    connected_data: tuple[CTFManager, Path, list[Project], list[User]]
) -> tuple[CTFManager, Path, list[Project], list[User]]:
    """Yield a CTFManager with 2 projects, 3 users, and destination directory.

    The manager contains following objects:
        Projects [enrolled]:
            - prj1 - [] - deleted
            - prj2 - [user2]
        Users [enrolled]:
            - user1 - [] - deleted
            - user2 - [prj2]
            - user3 - []

    :return: A CTFManager object, a path to the temporary directory,
    list of projects and users.
    :rtype: Iterator[tuple[CTFManager, Path, list[Project], list[User]]]
    """
    # init testing env
    ctf_mgr, tmp_path, prjs, usrs = connected_data
    prj_mgr = ctf_mgr.prj_mgr
    user_mgr = ctf_mgr.user_mgr

    # fill mgr with data
    prj_mgr.delete_project("prj1")
    user_mgr.delete_a_user("user1")

    # update list of objects
    usrs = user_mgr.get_docs()
    prjs = prj_mgr.get_docs()

    # yield data
    return ctf_mgr, tmp_path, prjs, usrs
