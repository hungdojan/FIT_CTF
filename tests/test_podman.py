import os
from pathlib import Path
from typing import Iterator

import pymongo.errors
import pytest
import yaml
from _pytest.fixtures import FixtureRequest

from fit_ctf_backend.ctf_manager import CTFManager
from fit_ctf_db_models.project import Project
from fit_ctf_db_models.user import User
from fit_ctf_utils.container_client.podman_client import PodmanClient

if os.getenv("ENABLE_PODMAN_CLIENT_TESTING") == "0":
    pytest.skip("Podman testing not enabled.", allow_module_level=True)


@pytest.fixture(scope="module")
def empty_podman_data(
    request: FixtureRequest,
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[CTFManager, Path, list[Project], list[User]]:
    """Init CTFManager.

    :return: A CTFManager object, a path to the temporary directory,
    list of projects and users.
    :rtype: Iterator[tuple[CTFManager, Path, list[Project], list[User]]]
    """
    os.environ["CONTAINER_CLIENT"] = "podman"

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

    # init testing env and clear database (just in case)
    try:
        ctf_mgr = CTFManager(db_host, db_name)
    except pymongo.errors.ServerSelectionTimeoutError:
        pytest.exit("DB is probably not running")

    ctf_mgr.prj_mgr.remove_docs_by_filter()
    ctf_mgr.user_mgr.remove_docs_by_filter()
    ctf_mgr.user_config_mgr.remove_docs_by_filter()

    # make a shadow dir
    (tmp_path_factory.getbasetemp() / "shadow").mkdir()
    request.addfinalizer(teardown)
    return ctf_mgr, tmp_path_factory.getbasetemp(), [], []


@pytest.fixture(scope="module")
def init_podman_data(
    empty_podman_data: tuple[CTFManager, Path, list[Project], list[User]]
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
    ctf_mgr, tmp_path, prjs, usrs = empty_podman_data
    prj_mgr = ctf_mgr.prj_mgr
    user_mgr = ctf_mgr.user_mgr
    user_config_mgr = ctf_mgr.user_config_mgr

    def add_data():
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
        return prjs, usrs

    def connect_data():
        user_config_mgr.enroll_multiple_users_to_project(
            [u.username for u in usrs[1:]], prjs[0].name
        )
        user_config_mgr.enroll_multiple_users_to_project(
            [u.username for u in usrs[:-1]], prjs[1].name
        )

    def include_modules(prjs):
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

    # fill mgr with data
    prjs, usrs = add_data()
    connect_data()
    include_modules(prjs)

    usrs = user_mgr.get_docs()
    prjs = prj_mgr.get_docs()

    # yield data
    return ctf_mgr, tmp_path, prjs, usrs


@pytest.fixture(scope="function")
def podman_data(
    init_podman_data: tuple[CTFManager, Path, list[Project], list[User]],
) -> Iterator[tuple[CTFManager, Path, list[Project], list[User]]]:
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
    ctf_mgr, tmp_path, prjs, usrs = init_podman_data
    prj_mgr = ctf_mgr.prj_mgr
    user_config_mgr = ctf_mgr.user_config_mgr

    def teardown():
        for prj in prj_mgr.get_docs():
            if prj_mgr.project_is_running(prj):
                prj_mgr.stop_project(prj)
                for usr in prj_mgr.get_active_users_for_project(prj):
                    if user_config_mgr.user_instance_is_running(usr, prj):
                        user_config_mgr.stop_user_instance(usr, prj)
                # user_config_mgr.stop_all_user_instances(prj)

    # yield data
    yield ctf_mgr, tmp_path, prjs, usrs
    teardown()


# ================ END OF FIXTURES ================


def test_podman_basic(podman_data: tuple[CTFManager, Path, list[Project], list[User]]):
    ctf_mgr, _, prjs, _ = podman_data
    prj_mgr = ctf_mgr.prj_mgr
    user_config_mgr = ctf_mgr.user_config_mgr
    for p in prjs:
        assert not prj_mgr.project_is_running(p)
        users = prj_mgr.get_active_users_for_project(p)
        assert not all([user_config_mgr.user_instance_is_running(u, p) for u in users])


def test_start_project(podman_data: tuple[CTFManager, Path, list[Project], list[User]]):
    ctf_mgr, _, prjs, _ = podman_data
    prj_mgr = ctf_mgr.prj_mgr
    assert not prj_mgr.project_is_running(prjs[0])

    prj_mgr.start_project(prjs[0])
    assert prj_mgr.project_is_running(prjs[0])


def test_restart_project(
    podman_data: tuple[CTFManager, Path, list[Project], list[User]]
):
    ctf_mgr, _, prjs, _ = podman_data
    prj_mgr = ctf_mgr.prj_mgr
    assert not prj_mgr.project_is_running(prjs[0])

    prj_mgr.restart_project(prjs[0])
    assert prj_mgr.project_is_running(prjs[0])

    prj_mgr.restart_project(prjs[0])
    assert prj_mgr.project_is_running(prjs[0])


def test_stop_project(podman_data: tuple[CTFManager, Path, list[Project], list[User]]):
    ctf_mgr, _, prjs, _ = podman_data
    prj_mgr = ctf_mgr.prj_mgr
    assert not prj_mgr.project_is_running(prjs[0])

    prj_mgr.start_project(prjs[0])
    assert prj_mgr.project_is_running(prjs[0])

    prj_mgr.stop_project(prjs[0])
    assert not prj_mgr.project_is_running(prjs[0])


def test_compile_and_build_project(
    podman_data: tuple[CTFManager, Path, list[Project], list[User]]
):
    ctf_mgr, _, prjs, _ = podman_data
    prj_mgr = ctf_mgr.prj_mgr

    with open(prjs[0].compose_filepath, "r") as f:
        data = yaml.safe_load(f)
        assert set(data["services"].keys()) == set(["admin"])

    prj_mgr.start_project(prjs[0])

    assert len(prj_mgr.c_client.compose_ps(str(prjs[0].compose_filepath))) == 1
    prj_mgr.stop_project(prjs[0])

    prj_mgr.compile_project(prjs[0])
    with open(prjs[0].compose_filepath, "r") as f:
        data = yaml.safe_load(f)
        assert set(data["services"].keys()) == set(
            ["admin"] + [m.name for m in prj_mgr.list_project_modules(prjs[0].name)]
        )

    prj_mgr.build_project(prjs[0])
    prj_mgr.start_project(prjs[0])

    assert len(prj_mgr.c_client.compose_ps(str(prjs[0].compose_filepath))) == 3


def test_get_resource_usage(
    podman_data: tuple[CTFManager, Path, list[Project], list[User]]
):
    ctf_mgr, _, prjs, _ = podman_data
    prj_mgr = ctf_mgr.prj_mgr

    print(prj_mgr.get_resource_usage(prjs[0]))
    assert not prj_mgr.get_resource_usage(prjs[0])

    prj_mgr.start_project(prjs[0])
    data = prj_mgr.get_resource_usage(prjs[0])
    assert data and prjs[0].name in data[0]["name"]


def test_project_ps(podman_data: tuple[CTFManager, Path, list[Project], list[User]]):
    ctf_mgr, _, prjs, _ = podman_data
    prj_mgr = ctf_mgr.prj_mgr

    data = prj_mgr.get_ps_data(prjs[0])
    assert not data[1:]

    prj_mgr.start_project(prjs[0])
    data = prj_mgr.get_ps_data(prjs[0])
    assert data[1:]


def test_delete_project_while_on(
    podman_data: tuple[CTFManager, Path, list[Project], list[User]]
):
    ctf_mgr, _, prjs, _ = podman_data
    prj_mgr = ctf_mgr.prj_mgr

    assert not prj_mgr.project_is_running(prjs[1])

    prj_mgr.start_project(prjs[1])
    assert prj_mgr.project_is_running(prjs[1])

    prj_mgr.delete_project(prjs[1])
    assert not PodmanClient.ps(prjs[1].name)[1:]
