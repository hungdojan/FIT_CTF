import os
from pathlib import Path

import pymongo.errors
import pytest
from _pytest.fixtures import FixtureRequest
from click.testing import CliRunner
from dotenv import load_dotenv

from fit_ctf_backend.ctf_manager import CTFManager
from fit_ctf_utils.constants import get_db_info
from fit_ctf_utils.data_parser.yaml_parser import YamlParser
from fit_ctf_utils.types import PathDict

from . import CLIData, FixtureData, fixture_path

load_dotenv()


@pytest.fixture(scope="session")
def workdir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.getbasetemp()


@pytest.fixture
def empty_data(
    request: FixtureRequest,
    workdir: Path,
) -> FixtureData:
    """Yield an empty CTFManager object.

    :return: A CTFManager object, a path to the temporary directory,
    list of projects and users.
    :rtype: Iterator[FixtureData]
    """

    def teardown():
        # teardown ctf_mgr
        ctf_mgr.prj_mgr.delete_all()
        ctf_mgr.user_mgr.delete_all()
        ctf_mgr.user_enrollment_mgr.delete_all()

    # get data
    db_host, db_name = get_db_info()
    if not db_host:
        pytest.exit("DB_HOST environment variable is not set!")
    os.environ["LOG_DEST"] = str(workdir.resolve())

    YamlParser.init_parser()
    paths = PathDict(
        **{
            "projects": workdir / "share" / "project",
            "users": workdir / "share" / "user",
            "modules": workdir / "share" / "module",
        }
    )

    # init testing env and clear database (just in case)
    try:
        ctf_mgr = CTFManager(db_host, db_name, paths)
    except pymongo.errors.ServerSelectionTimeoutError:
        pytest.exit("DB is probably not running")

    ctf_mgr.prj_mgr.remove_docs_by_filter()
    ctf_mgr.user_mgr.remove_docs_by_filter()
    ctf_mgr.user_enrollment_mgr.remove_docs_by_filter()

    # make a shadow dir
    request.addfinalizer(teardown)
    return ctf_mgr, workdir


@pytest.fixture
def project_data(
    empty_data: FixtureData,
) -> FixtureData:
    """Yield a CTFManager with 2 projects and destination directory.

    The manager contains following objects:
        Projects [enrolled]:
            - prj1 - []
            - prj2 - []

    :return: A CTFManager object, a path to the temporary directory,
    list of projects and users.
    :rtype: Iterator[FixtureData]
    """

    # init testing env
    ctf_mgr, tmp_path = empty_data
    ctf_mgr.setup_env_from_file(fixture_path() / "project_data.yaml")
    assert len(ctf_mgr.prj_mgr.get_docs()) == 2

    # yield data
    return ctf_mgr, tmp_path


@pytest.fixture
def user_data(
    empty_data: FixtureData,
) -> FixtureData:
    """Yield a CTFManager with 3 users and destination directory.

    The manager contains following objects:
        Users [enrolled]:
            - user1 - []
            - user2 - []
            - user3 - []

    :return: A CTFManager object, a path to the temporary directory,
        list of projects and users.
    :rtype: Iterator[FixtureData]
    """
    # init testing env
    ctf_mgr, tmp_path = empty_data
    ctf_mgr.setup_env_from_file(fixture_path() / "user_data.yaml")
    assert len(ctf_mgr.user_mgr.get_docs()) == 3

    # yield data
    return ctf_mgr, tmp_path


@pytest.fixture
def unconnected_data(
    empty_data: FixtureData,
) -> FixtureData:
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
    :rtype: Iterator[FixtureData]
    """
    # init testing env
    ctf_mgr, tmp_path = empty_data
    ctf_mgr.setup_env_from_file(fixture_path() / "unconnected_data.yaml")
    assert (
        len(ctf_mgr.prj_mgr.get_docs()) == 2 and len(ctf_mgr.user_mgr.get_docs()) == 3
    )

    # yield data
    return ctf_mgr, tmp_path


@pytest.fixture
def connected_data(
    empty_data: FixtureData,
) -> FixtureData:
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
    :rtype: Iterator[FixtureData]
    """
    # init testing env
    ctf_mgr, tmp_path = empty_data
    ctf_mgr.setup_env_from_file(fixture_path() / "connected_data.yaml")

    assert len(ctf_mgr.user_enrollment_mgr.get_enrolled_projects("user2")) == 2

    # yield data
    return ctf_mgr, tmp_path


@pytest.fixture
def cli_data(connected_data: FixtureData) -> CLIData:
    ctf_mgr, tmp_path = connected_data
    os.environ.update(
        {
            "PROJECT_SHARE_DIR": str((tmp_path / "share" / "project").resolve()),
            "USER_SHARE_DIR": str((tmp_path / "share" / "user").resolve()),
            "MODULE_SHARE_DIR": str((tmp_path / "share" / "module").resolve()),
        }
    )
    return ctf_mgr, tmp_path, CliRunner()


@pytest.fixture
def empty_cli_data(empty_data: FixtureData) -> CLIData:
    ctf_mgr, tmp_path = empty_data
    os.environ.update(
        {
            "PROJECT_SHARE_DIR": str((tmp_path / "share" / "project").resolve()),
            "USER_SHARE_DIR": str((tmp_path / "share" / "user").resolve()),
            "MODULE_SHARE_DIR": str((tmp_path / "share" / "module").resolve()),
        }
    )
    return ctf_mgr, tmp_path, CliRunner()


# @pytest.fixture
# def modules_data(
#     connected_data: FixtureData,
# ) -> FixtureData:
#     """Yield a CTFManager with 2 projects, 3 users, and destination directory.
#
#     The manager contains following objects:
#         Projects [enrolled] [modules]:
#             - prj1 - [user2, user3] [prj1_prj_module1, prj1_prj_module2]
#             - prj2 - [user1, user2] [prj2_prj_module1, prj2_prj_module2]
#         Users [enrolled] [modules]:
#             - user1 - [prj2]        [prj2_module1]
#             - user2 - [prj1, prj2]  [prj2_module1, prj2_module2, prj1_module1]
#             - user3 - [prj1]        [prj1_module1, prj1_module2]
#
#     :return: A CTFManager object, a path to the temporary directory,
#     list of projects and users.
#     :rtype: Iterator[FixtureData]
#     """
#     # init testing env
#     ctf_mgr, tmp_path, prjs, usrs = connected_data
#     prj_mgr = ctf_mgr.prj_mgr
#     user_mgr = ctf_mgr.user_mgr
#     user_enrollment_mgr = ctf_mgr.user_enrollment_mgr
#
#     # fill mgr with data
#     for prj in prjs:
#         for i in range(2):
#             prj_mgr.create_project_module(prj.name, f"{prj.name}_prj_module{i+1}")
#             prj_mgr.create_user_module(prj.name, f"{prj.name}_module{i+1}")
#
#     usrs = user_mgr.get_docs()
#     prjs = prj_mgr.get_docs()
#
#     user_enrollment_mgr.add_module(
#         usrs[0], prjs[1], prjs[1].get_user_module(f"{prjs[1].name}_module1")
#     )
#     user_enrollment_mgr.add_module(
#         usrs[1], prjs[1], prjs[1].get_user_module(f"{prjs[1].name}_module1")
#     )
#     user_enrollment_mgr.add_module(
#         usrs[1], prjs[1], prjs[1].get_user_module(f"{prjs[1].name}_module2")
#     )
#
#     user_enrollment_mgr.add_module(
#         usrs[1], prjs[0], prjs[0].get_user_module(f"{prjs[0].name}_module1")
#     )
#     user_enrollment_mgr.add_module(
#         usrs[2], prjs[0], prjs[0].get_user_module(f"{prjs[0].name}_module1")
#     )
#     user_enrollment_mgr.add_module(
#         usrs[2], prjs[0], prjs[0].get_user_module(f"{prjs[0].name}_module2")
#     )
#
#     [user_enrollment_mgr.compile_compose(u, prjs[0]) for u in usrs[1:]]
#     [user_enrollment_mgr.compile_compose(u, prjs[1]) for u in usrs[:-1]]
#
#     # yield data
#     return ctf_mgr, tmp_path, prjs, usrs
#
#
# @pytest.fixture
# def deleted_data(
#     connected_data: FixtureData,
# ) -> FixtureData:
#     """Yield a CTFManager with 2 projects, 3 users, and destination directory.
#
#     The manager contains following objects:
#         Projects [enrolled]:
#             - prj1 - [] - deleted
#             - prj2 - [user2]
#         Users [enrolled]:
#             - user1 - [] - deleted
#             - user2 - [prj2]
#             - user3 - []
#
#     :return: A CTFManager object, a path to the temporary directory,
#     list of projects and users.
#     :rtype: Iterator[FixtureData]
#     """
#     # init testing env
#     ctf_mgr, tmp_path, prjs, usrs = connected_data
#     prj_mgr = ctf_mgr.prj_mgr
#     user_mgr = ctf_mgr.user_mgr
#
#     # fill mgr with data
#     prj_mgr.delete_project("prj1")
#     user_mgr.delete_a_user("user1")
#
#     # update list of objects
#     usrs = user_mgr.get_docs()
#     prjs = prj_mgr.get_docs()
#
#     # yield data
#     return ctf_mgr, tmp_path, prjs, usrs
