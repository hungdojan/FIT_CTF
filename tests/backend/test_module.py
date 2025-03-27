from pathlib import Path

import pytest

from fit_ctf_templates import TEMPLATE_DIRNAME
from fit_ctf_utils.exceptions import (
    ModuleExistsException,
    ModuleInUseException,
    ModuleNotExistsException,
)

from tests import FixtureData


def test_base_modules(empty_data: FixtureData):
    # init testing env
    ctf_mgr, _ = empty_data
    assert ctf_mgr._paths["modules"].is_dir()
    module_names = [path.name for path in ctf_mgr._paths["modules"].iterdir()]
    assert set(module_names) == {"base", "base_ssh"}


def test_list_modules(empty_data: FixtureData):
    ctf_mgr, _ = empty_data
    for name, path in ctf_mgr.module_mgr.list_modules().items():
        assert name in {"base", "base_ssh"}
        assert path.is_dir()


def test_create_module(
    empty_data: FixtureData,
):
    # init testing env
    ctf_mgr, _ = empty_data
    module_mgr = ctf_mgr.module_mgr
    with pytest.raises(ModuleExistsException):
        module_mgr.create_module("base")
    module_mgr.create_module("new_module")
    module_path = module_mgr.get_path("new_module")
    assert module_path.is_dir()
    assert set([path.name for path in module_path.iterdir()]) == set(
        [path.name for path in (Path(TEMPLATE_DIRNAME) / "v1" / "modules").iterdir()]
    )

    # teardown
    module_mgr.remove_module("new_module")


def test_reference_count(connected_data: FixtureData):
    ctf_mgr, _ = connected_data
    prj = ctf_mgr.prj_mgr.get_docs()[0]
    assert ctf_mgr.module_mgr.reference_count(prj.name) == {"base": 1, "base_ssh": 2}
    assert ctf_mgr.module_mgr.reference_count(None) == {"base": 2, "base_ssh": 4}

    ctf_mgr.user_enrollment_mgr.cancel_user_enrollment(
        ctf_mgr.user_enrollment_mgr.get_user_enrollments_for_project(prj)[0], prj
    )

    assert ctf_mgr.module_mgr.reference_count(prj.name) == {"base": 1, "base_ssh": 1}


def test_remove_module(connected_data: FixtureData):
    ctf_mgr, _ = connected_data
    for prj in ctf_mgr.prj_mgr.get_docs():
        ctf_mgr.user_enrollment_mgr.cancel_all_project_enrollments(prj)
    module_path = ctf_mgr.module_mgr.list_modules()["base_ssh"]
    assert module_path.is_dir()
    ctf_mgr.module_mgr.remove_module("base_ssh")
    assert not module_path.is_dir()


def test_error_states(connected_data: FixtureData):
    ctf_mgr, _ = connected_data
    module_mgr = ctf_mgr.module_mgr
    with pytest.raises(ModuleExistsException):
        module_mgr.create_module("base")
    with pytest.raises(ModuleNotExistsException):
        module_mgr.get_path("random_module")
    with pytest.raises(ModuleInUseException):
        module_mgr.remove_module("base_ssh")
