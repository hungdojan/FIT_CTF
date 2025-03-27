import pathlib
import tempfile
import zipfile

import pytest

from fit_ctf_utils.data_parser.yaml_parser import YamlParser
from fit_ctf_utils.exceptions import CTFException, ProjectNotExistException
from tests import FixtureData, fixture_path


def test_export_project(connected_data: FixtureData):
    ctf_mgr, tmp_path = connected_data
    zip_path = tmp_path / "project.zip"
    with pytest.raises(ProjectNotExistException):
        ctf_mgr.export_project("prj3", str(zip_path.resolve()))

    assert not zip_path.exists()
    ctf_mgr.export_project("prj2", str(zip_path.resolve()))
    assert zip_path.exists()

    with tempfile.TemporaryDirectory() as tmp_dir:
        with zipfile.ZipFile(zip_path, "r") as zf:
            assert "database_dump.yaml" in zf.namelist()
            zf.extractall(tmp_dir)
            data = YamlParser.load_data_file(
                pathlib.Path(tmp_dir) / "database_dump.yaml"
            )
            assert len(data["enrollments"]) == 2
            assert set(data["modules"]) == {"base", "base_ssh"}
            assert len(data["users"]) == 2
            assert data["project"]["name"] == "prj2"

            assert len(list((pathlib.Path(tmp_dir) / "user").iterdir())) == 2
            assert len(list((pathlib.Path(tmp_dir) / "module").iterdir())) == 2


def test_import_project(empty_data: FixtureData):
    ctf_mgr, tmp_path = empty_data
    # generated from the previous test case
    zip_path = tmp_path / "project.zip"
    assert not ctf_mgr.prj_mgr.get_docs()
    assert not ctf_mgr.user_mgr.get_docs()
    assert not ctf_mgr.user_enrollment_mgr.get_docs()

    ctf_mgr.import_project(zip_path)

    assert ctf_mgr.prj_mgr.get_project("prj2")
    assert len(ctf_mgr.user_mgr.get_docs()) == 2
    assert len(ctf_mgr.user_enrollment_mgr.get_docs()) == 2

    # clean up here since the tmp_path is defined for the session scope
    zip_path.unlink()


def test_setup_env_from_file(empty_data: FixtureData):
    ctf_mgr, _ = empty_data

    ctf_mgr.setup_env_from_file(fixture_path() / "project_data.yaml")
    with pytest.raises(CTFException):
        ctf_mgr.setup_env_from_file(fixture_path() / "project_data.yaml")

    ctf_mgr.setup_env_from_file(fixture_path() / "user_data.yaml")
    with pytest.raises(CTFException):
        ctf_mgr.setup_env_from_file(fixture_path() / "user_data.yaml")

    ctf_mgr.prj_mgr.delete_all()
    ctf_mgr.user_mgr.delete_all()

    new_users = ctf_mgr.setup_env_from_file(fixture_path() / "connected_data.yaml")
    assert len(ctf_mgr.prj_mgr.get_docs()) == 2
    assert len(new_users) == 3
    assert len(ctf_mgr.user_enrollment_mgr.get_docs()) == 4

    with pytest.raises(CTFException):
        ctf_mgr.setup_env_from_file(fixture_path() / "user_data.yaml")
        ctf_mgr.setup_env_from_file(fixture_path() / "project_data.yaml")
    ctf_mgr.setup_env_from_file(fixture_path() / "user_data.yaml", exist_ok=True)
    ctf_mgr.setup_env_from_file(fixture_path() / "project_data.yaml", exist_ok=True)

    assert not ctf_mgr.setup_env_from_file(
        fixture_path() / "user_data.yaml", dry_run=True
    )
