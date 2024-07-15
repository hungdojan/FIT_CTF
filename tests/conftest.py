from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator

import pytest
from dotenv import load_dotenv

from fit_ctf_backend.ctf_manager import CTFManager
from fit_ctf_db_models.project import Project
from fit_ctf_db_models.user import User

load_dotenv()


@pytest.fixture
def empty_data(
    tmp_path: Path,
) -> Iterator[tuple[CTFManager, Path, list[Project], list[User]]]:
    """Yield an empty CTFManager object.

    :return: A CTFManager object, a path to the temporary directory,
    list of projects and users.
    :rtype: Iterator[tuple[CTFManager, Path, list[Project], list[User]]]
    """
    # get data
    db_host = os.getenv("DB_HOST")
    db_name = os.getenv("DB_TEST_NAME", "test-ctf-db")
    if not db_host:
        pytest.exit()

    # init testing env
    ctf_mgr = CTFManager(db_host, db_name)
    # make a shadow dir
    (tmp_path / "shadow").mkdir()
    yield ctf_mgr, tmp_path, [], []

    # teardown ctf_mgr
    ctf_mgr.user_mgr.delete_all()
    ctf_mgr.prj_mgr.delete_all()
    ctf_mgr.user_config_mgr.clear_database()


@pytest.fixture
def project_data(
    empty_data: tuple[CTFManager, Path, list[Project], list[User]]
) -> Iterator[tuple[CTFManager, Path, list[Project], list[User]]]:
    """Yield a CTFManager with 2 projects and destination directory.

    The manager contains following objects:
        Projects:
            - prj1
            - prj2

    :return: A CTFManager object, a path to the temporary directory,
    list of projects and users.
    :rtype: Iterator[tuple[CTFManager, Path, list[Project], list[User]]]
    """

    # init testing env
    ctf_mgr, tmp_path, prjs, usrs = empty_data
    prj_mgr = ctf_mgr.prj_mgr

    # fill mgr with data
    data = {
        "name": "prj1",
        "dest_dir": str(tmp_path.resolve()),
        "max_nof_users": 5,
        "starting_port_bind": -1,
        "volume_mount_dirname": "_mounts",
        "dir_name": "",
        "description": "",
        "compose_file": "server_compose.yaml",
    }
    prjs.append(prj_mgr.init_project(**data))
    data = {
        "name": "prj2",
        "dest_dir": str(tmp_path.resolve()),
        "max_nof_users": 5,
        "starting_port_bind": -1,
        "volume_mount_dirname": "_mounts",
        "dir_name": "",
        "description": "",
        "compose_file": "server_compose.yaml",
    }
    prjs.append(prj_mgr.init_project(**data))

    # yield data
    yield ctf_mgr, tmp_path, prjs, usrs


@pytest.fixture
def user_data(
    empty_data: tuple[CTFManager, Path, list[Project], list[User]]
) -> Iterator[tuple[CTFManager, Path, list[Project], list[User]]]:
    """Yield a CTFManager with 3 users and destination directory.

    :return: A CTFManager object, a path to the temporary directory,
    list of projects and users.
    :rtype: Iterator[tuple[CTFManager, Path, list[Project], list[User]]]
    """
    # init testing env
    ctf_mgr, tmp_path, prjs, usrs = empty_data

    # fill mgr with data

    # yield data
    yield ctf_mgr, tmp_path, prjs, usrs


@pytest.fixture
def basic_data(
    empty_data: tuple[CTFManager, Path, list[Project], list[User]]
) -> Iterator[tuple[CTFManager, Path, list[Project], list[User]]]:
    """Yield a CTFManager with 2 projects, 3 users, and destination directory.

    :return: A CTFManager object, a path to the temporary directory,
    list of projects and users.
    :rtype: Iterator[tuple[CTFManager, Path, list[Project], list[User]]]
    """
    # init testing env
    ctf_mgr, tmp_path, prjs, usrs = empty_data

    # fill mgr with data

    # yield data
    yield ctf_mgr, tmp_path, prjs, usrs
