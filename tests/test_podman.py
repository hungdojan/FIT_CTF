import os
from pathlib import Path
from typing import Iterator

import pymongo.errors
import pytest
import yaml
from _pytest.fixtures import FixtureRequest

from fit_ctf_backend.ctf_manager import CTFManager
from fit_ctf_backend.exceptions import UserNotEnrolledToProjectException
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

    # fill mgr with data
    prjs, usrs = add_data()
    connect_data()
    include_modules(prjs)

    usrs = user_mgr.get_docs()
    prjs = prj_mgr.get_docs()

    # yield data
    return ctf_mgr, tmp_path, prjs, usrs


@pytest.fixture(scope="module")
def build_podman_data(
    init_podman_data: tuple[CTFManager, Path, list[Project], list[User]]
) -> tuple[CTFManager, Path, list[Project], list[User]]:
    # init testing env
    ctf_mgr, tmp_path, _, _ = init_podman_data
    prj_mgr = ctf_mgr.prj_mgr
    user_mgr = ctf_mgr.user_mgr
    user_config_mgr = ctf_mgr.user_config_mgr

    for prj in prj_mgr.get_docs():
        prj_mgr.compile_project(prj)
        prj_mgr.build_project(prj)
        for usr in prj_mgr.get_active_users_for_project(prj):
            user_config_mgr.compile_compose(usr, prj)
            user_config_mgr.build_user_instance(usr, prj)

    # yield data
    return ctf_mgr, tmp_path, prj_mgr.get_docs(), user_mgr.get_docs()


@pytest.fixture(scope="function")
def podman_data(
    init_podman_data: tuple[CTFManager, Path, list[Project], list[User]],
) -> Iterator[tuple[CTFManager, Path, list[Project], list[User]]]:
    """Yield a CTFManager with 2 projects, 3 users, and destination directory.

    All images are build.

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

    # yield data
    yield ctf_mgr, tmp_path, prjs, usrs
    teardown()


@pytest.fixture(scope="function")
def podman_updated_data(
    build_podman_data: tuple[CTFManager, Path, list[Project], list[User]],
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
    ctf_mgr, tmp_path, prjs, usrs = build_podman_data
    prj_mgr = ctf_mgr.prj_mgr
    user_config_mgr = ctf_mgr.user_config_mgr

    def teardown():
        for prj in prj_mgr.get_docs():
            if prj_mgr.project_is_running(prj):
                prj_mgr.stop_project(prj)
            for usr in prj_mgr.get_active_users_for_project(prj):
                if user_config_mgr.user_instance_is_running(usr, prj):
                    user_config_mgr.stop_user_instance(usr, prj)

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


def test_get_images(
    podman_updated_data: tuple[CTFManager, Path, list[Project], list[User]]
):
    def calculate_nof_images(prj: Project):
        # admin node + shared user node
        nodes = 1
        nodes += len(prj.project_modules.keys())
        # get active modules
        user_modules = {k: 0 for k in prj.user_modules.keys()}
        for usr in prj_mgr.get_active_users_for_project(prj):
            nodes += 1  # user login node
            for module_name in user_config_mgr.get_user_config(prj, usr).modules.keys():
                user_modules[module_name] += 1

        return nodes + sum(user_modules.values())

    ctf_mgr, _, prjs, _ = podman_updated_data
    prj_mgr = ctf_mgr.prj_mgr
    user_config_mgr = ctf_mgr.user_config_mgr

    total_images = 0
    for prj in prjs:
        nof_images = calculate_nof_images(prj)
        assert len(PodmanClient.get_images(prj.name)) == nof_images
        total_images += nof_images

    assert len(PodmanClient.get_images([p.name for p in prjs])) == total_images


def test_get_networks(
    podman_updated_data: tuple[CTFManager, Path, list[Project], list[User]]
):
    def calculate_nof_networks(prj: Project):
        # project's network + a private network each user has
        return 1 + len(prj_mgr.get_active_users_for_project(prj))

    ctf_mgr, _, prjs, _ = podman_updated_data
    prj_mgr = ctf_mgr.prj_mgr
    user_config_mgr = ctf_mgr.user_config_mgr

    total_networks = 0
    for prj in prjs:
        for usr in prj_mgr.get_active_users_for_project(prj):
            user_config_mgr.start_user_instance(usr, prj)
        nof_networks = calculate_nof_networks(prj)
        networks = PodmanClient.get_networks(prj.name)
        assert len(networks) == nof_networks
        total_networks += nof_networks

    assert len(PodmanClient.get_networks([p.name for p in prjs])) == total_networks


def test_compose_ps_json(
    podman_updated_data: tuple[CTFManager, Path, list[Project], list[User]]
):
    ctf_mgr, _, prjs, _ = podman_updated_data
    prj_mgr = ctf_mgr.prj_mgr

    prj_mgr.start_project(prjs[0])
    json_data = PodmanClient.compose_ps_json(str(prjs[0].compose_filepath))
    assert len(json_data) == 1 + len(prjs[0].project_modules.keys())
    names = [jd["Names"] for jd in json_data]
    assert all([all([s.startswith(prjs[0].name) for s in n]) for n in names])


def test_start_user_instance(
    podman_updated_data: tuple[CTFManager, Path, list[Project], list[User]]
):
    ctf_mgr, _, prjs, usrs = podman_updated_data
    user_config_mgr = ctf_mgr.user_config_mgr

    assert not user_config_mgr.user_instance_is_running(usrs[0], prjs[1])

    with pytest.raises(UserNotEnrolledToProjectException):
        user_config_mgr.start_user_instance(usrs[0], prjs[0])

    user_config_mgr.start_user_instance(usrs[0], prjs[1])
    assert user_config_mgr.user_instance_is_running(usrs[0], prjs[1])

    user_config_mgr.enroll_user_to_project(usrs[0].username, prjs[0].name)

    assert not (
        Path(prjs[0].config_root_dir) / f"{usrs[0].username}_compose.yaml"
    ).exists()
    assert not user_config_mgr.user_instance_is_running(usrs[0], prjs[0])

    user_config_mgr.start_user_instance(usrs[0], prjs[0])
    assert user_config_mgr.user_instance_is_running(usrs[0], prjs[0])
    assert (Path(prjs[0].config_root_dir) / f"{usrs[0].username}_compose.yaml").exists()

    # clean up
    user_config_mgr.cancel_user_enrollment(usrs[0], prjs[0])
    with pytest.raises(UserNotEnrolledToProjectException):
        user_config_mgr.user_instance_is_running(usrs[0], prjs[0])
    assert not PodmanClient.get_networks(f"{prjs[0].name}_{usrs[0].username}")


def test_user_instance_is_running(
    podman_updated_data: tuple[CTFManager, Path, list[Project], list[User]]
):
    ctf_mgr, _, prjs, usrs = podman_updated_data
    user_config_mgr = ctf_mgr.user_config_mgr

    compose_file = Path(prjs[0].config_root_dir) / f"{usrs[1].username}_compose.yaml"
    assert not user_config_mgr.user_instance_is_running(usrs[0], prjs[1])

    user_config_mgr.start_user_instance(usrs[0], prjs[1])
    assert user_config_mgr.user_instance_is_running(usrs[0], prjs[1])

    with pytest.raises(UserNotEnrolledToProjectException):
        user_config_mgr.user_instance_is_running(usrs[0], prjs[0])


def test_stop_user_instance(
    podman_updated_data: tuple[CTFManager, Path, list[Project], list[User]]
):
    ctf_mgr, _, prjs, usrs = podman_updated_data
    user_config_mgr = ctf_mgr.user_config_mgr

    assert not user_config_mgr.user_instance_is_running(usrs[0], prjs[1])

    user_config_mgr.start_user_instance(usrs[0], prjs[1])
    assert user_config_mgr.user_instance_is_running(usrs[0], prjs[1])

    user_config_mgr.stop_user_instance(usrs[0], prjs[1])
    assert not user_config_mgr.user_instance_is_running(usrs[0], prjs[1])

    with pytest.raises(UserNotEnrolledToProjectException):
        user_config_mgr.stop_user_instance(usrs[0], prjs[0])


def test_restart_user_instance(
    podman_updated_data: tuple[CTFManager, Path, list[Project], list[User]]
):
    ctf_mgr, _, prjs, usrs = podman_updated_data
    user_config_mgr = ctf_mgr.user_config_mgr

    assert not user_config_mgr.user_instance_is_running(usrs[0], prjs[1])

    user_config_mgr.start_user_instance(usrs[0], prjs[1])
    assert user_config_mgr.user_instance_is_running(usrs[0], prjs[1])

    user_config_mgr.stop_user_instance(usrs[0], prjs[1])


def test_build_user_instance(
    podman_updated_data: tuple[CTFManager, Path, list[Project], list[User]]
):
    ctf_mgr, _, prjs, usrs = podman_updated_data
    user_config_mgr = ctf_mgr.user_config_mgr

    with pytest.raises(UserNotEnrolledToProjectException):
        user_config_mgr.build_user_instance(usrs[0], prjs[0])


def test_stop_all_user_instances(
    podman_updated_data: tuple[CTFManager, Path, list[Project], list[User]]
):
    ctf_mgr, _, prjs, usrs = podman_updated_data
    user_config_mgr = ctf_mgr.user_config_mgr

    assert not user_config_mgr.user_instance_is_running(usrs[0], prjs[1])

    user_config_mgr.restart_user_instance(usrs[0], prjs[1])
    assert user_config_mgr.user_instance_is_running(usrs[0], prjs[1])

    with pytest.raises(UserNotEnrolledToProjectException):
        user_config_mgr.restart_user_instance(usrs[0], prjs[0])


def test_delete_project_while_on(
    podman_updated_data: tuple[CTFManager, Path, list[Project], list[User]]
):
    ctf_mgr, _, prjs, _ = podman_updated_data
    prj_mgr = ctf_mgr.prj_mgr
    user_config_mgr = ctf_mgr.user_config_mgr

    assert not prj_mgr.project_is_running(prjs[1])

    prj_mgr.start_project(prjs[1])
    assert prj_mgr.project_is_running(prjs[1])

    for usr in prj_mgr.get_active_users_for_project(prjs[1]):
        user_config_mgr.start_user_instance(usr, prjs[1])

    deleted_prj = prjs[1]
    prj_mgr.delete_project(deleted_prj)
    assert not PodmanClient.ps(deleted_prj.name)[1:]
    assert len(PodmanClient.get_images(deleted_prj.name)) == 0
    assert len(PodmanClient.get_networks(deleted_prj.name)) == 0


def test_cancel_multiple_enrollments(
    podman_updated_data: tuple[CTFManager, Path, list[Project], list[User]]
):
    ctf_mgr, _, prjs, _ = podman_updated_data
    prj_mgr = ctf_mgr.prj_mgr
    user_config_mgr = ctf_mgr.user_config_mgr

    assert not prj_mgr.project_is_running(prjs[0])

    prj_mgr.start_project(prjs[0])
    assert prj_mgr.project_is_running(prjs[0])

    for usr in prj_mgr.get_active_users_for_project(prjs[0]):
        user_config_mgr.start_user_instance(usr, prjs[0])

    users = prj_mgr.get_active_users_for_project(prjs[0])
    user_config_mgr.cancel_multiple_enrollments([u.username for u in users], prjs[0])

    for user in users:
        with pytest.raises(UserNotEnrolledToProjectException):
            user_config_mgr.user_instance_is_running(user, prjs[0])
        assert not PodmanClient.get_networks(f"{prjs[0].name}_{user.username}")

    assert prj_mgr.project_is_running(prjs[0])
    assert len(PodmanClient.get_images(prjs[0].name)) == 1 + len(
        prjs[0].project_modules.keys()
    )
