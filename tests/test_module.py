from pathlib import Path
import shutil

import pytest
import yaml

from fit_ctf_backend.ctf_manager import CTFManager
from fit_ctf_backend.exceptions import DirNotEmptyException, ModuleExistsException, ModuleNotExistsException
from fit_ctf_db_models.project import Project
from fit_ctf_db_models.user import User


def test_no_modules(connected_data: tuple[CTFManager, Path, list[Project], list[User]]):
    # init testing env
    ctf_mgr, _, prjs, _ = connected_data
    prj_mgr = ctf_mgr.prj_mgr

    for prj in prjs:
        assert len(prj_mgr.list_project_modules(prj.name)) == 0
        assert len(prj_mgr.list_user_modules(prj.name)) == 0
        assert not (Path(prj.config_root_dir) / "_modules").is_dir()


def test_create_project_module(
    connected_data: tuple[CTFManager, Path, list[Project], list[User]]
):
    # init testing env
    ctf_mgr, _, prjs, _ = connected_data
    prj_mgr = ctf_mgr.prj_mgr

    _root = Path(prjs[0].config_root_dir)

    assert len(prj_mgr.list_project_modules(prjs[0].name)) == 0
    assert (
        not (_root / "_modules").is_dir()
        or len(list((_root / "_modules").glob("*"))) == 0
    )

    module_name = "module1"
    module_dir = _root / "_modules" / f"prj_{module_name}"

    module_dir.mkdir(parents=True)
    (module_dir / "file").touch()

    with pytest.raises(DirNotEmptyException):
        module = prj_mgr.create_project_module(prjs[0].name, module_name)

    shutil.rmtree(module_dir)

    module = prj_mgr.create_project_module(prjs[0].name, module_name)
    assert module.name == module_name
    _root_dir = Path(prjs[0].config_root_dir) / module.root_dir
    assert (
        _root_dir.is_dir()
        and (_root_dir / module.build_dir_name).is_dir()
        and len([i for i in (_root_dir / module.build_dir_name).glob("*")]) > 0
        and len(list((_root_dir / module.build_dir_name).glob("*"))) > 0
    )
    assert len(prj_mgr.list_project_modules(prjs[0].name)) == 1
    assert (Path(prjs[0].config_root_dir) / "_modules" / f"prj_{module_name}").is_dir()

    with pytest.raises(ModuleExistsException):
        prj_mgr.create_project_module(prjs[0].name, module_name)


def test_list_project_modules(
    modules_data: tuple[CTFManager, Path, list[Project], list[User]]
):
    ctf_mgr, _, prjs, _ = modules_data
    prj_mgr = ctf_mgr.prj_mgr

    for prj in prjs:
        modules = prj_mgr.list_project_modules(prj.name)
        expected_names = [f"{prj.name}_prj_module{i+1}" for i in range(2)]
        module_names = [m.name for m in modules]
        assert set(expected_names) == set(module_names)
        assert set(
            [prj.get_project_module(m_name).name for m_name in expected_names]
        ) == set(module_names)


def test_remove_project_module(
    modules_data: tuple[CTFManager, Path, list[Project], list[User]]
):
    ctf_mgr, _, prjs, _ = modules_data
    prj_mgr = ctf_mgr.prj_mgr

    p_modules = prj_mgr.list_project_modules(prjs[0].name)
    assert len(p_modules) == 2

    module_to_remove = p_modules.pop(0)
    assert (Path(prjs[0].config_root_dir) / module_to_remove.root_dir).is_dir()
    prj_mgr.remove_project_module(prjs[0].name, module_to_remove.name)

    new_m_list = prj_mgr.list_project_modules(prjs[0].name)
    assert len(new_m_list) == 1
    assert set([m.name for m in new_m_list]).difference({module_to_remove.name})
    assert not (Path(prjs[0].config_root_dir) / module_to_remove.root_dir).is_dir()

    with pytest.raises(ModuleNotExistsException):
        prj_mgr.remove_project_module(prjs[0].name, module_to_remove.name)


def test_create_user_module(
    connected_data: tuple[CTFManager, Path, list[Project], list[User]]
):
    # init testing env
    ctf_mgr, _, prjs, _ = connected_data
    prj_mgr = ctf_mgr.prj_mgr

    _root = Path(prjs[0].config_root_dir)

    assert len(prj_mgr.list_user_modules(prjs[0].name)) == 0
    assert (
        not (_root / "_modules").is_dir()
        or len(list((_root / "_modules").glob("*"))) == 0
    )

    module_name = "module1"
    module_dir = _root / "_modules" / f"usr_{module_name}"

    module_dir.mkdir(parents=True)
    (module_dir / "file").touch()

    with pytest.raises(DirNotEmptyException):
        module = prj_mgr.create_user_module(prjs[0].name, module_name)

    shutil.rmtree(module_dir)

    module = prj_mgr.create_user_module(prjs[0].name, module_name)
    assert module.name == module_name
    _root_dir = Path(prjs[0].config_root_dir) / module.root_dir
    assert (
        _root_dir.is_dir()
        and (_root_dir / module.build_dir_name).is_dir()
        and len([i for i in (_root_dir / module.build_dir_name).glob("*")]) > 0
    )
    assert len(prj_mgr.list_user_modules(prjs[0].name)) == 1
    assert (Path(prjs[0].config_root_dir) / "_modules" / f"usr_{module_name}").is_dir()

    with pytest.raises(ModuleExistsException):
        prj_mgr.create_user_module(prjs[0].name, module_name)


def test_list_user_modules(
    modules_data: tuple[CTFManager, Path, list[Project], list[User]]
):
    ctf_mgr, _, prjs, _ = modules_data
    prj_mgr = ctf_mgr.prj_mgr

    for prj in prjs:
        modules = prj_mgr.list_user_modules(prj.name)
        expected_names = [f"{prj.name}_module{i+1}" for i in range(2)]
        module_names = [m.name for m in modules]
        assert set(expected_names) == set(module_names)
        assert set(
            [prj.get_user_module(m_name).name for m_name in expected_names]
        ) == set(module_names)


def test_remove_user_module(
    modules_data: tuple[CTFManager, Path, list[Project], list[User]]
):
    ctf_mgr, _, prjs, _ = modules_data
    prj_mgr = ctf_mgr.prj_mgr
    user_config_mgr = ctf_mgr.user_config_mgr

    p_modules = prj_mgr.list_user_modules(prjs[0].name)
    assert len(p_modules) == 2

    module_to_remove = None

    while p_modules:
        module_to_remove = p_modules.pop(0)
        assert (Path(prjs[0].config_root_dir) / module_to_remove.root_dir).is_dir()
        prj_mgr.remove_user_module(prjs[0].name, module_to_remove.name)

        new_m_list = prj_mgr.list_user_modules(prjs[0].name)
        assert len(new_m_list) == len(p_modules)
        assert module_to_remove.name not in [m.name for m in new_m_list]
        assert not (Path(prjs[0].config_root_dir) / module_to_remove.root_dir).is_dir()

        u_ids = [u.id for u in prj_mgr.get_active_users_for_project(prjs[0])]
        ucs = user_config_mgr.get_docs(
            **{"user_id.$id": {"$in": u_ids}, "project_id.$id": prjs[0].id}
        )
        assert all([uc.modules.get(module_to_remove.name, None) is None for uc in ucs])

    if module_to_remove is not None:
        with pytest.raises(ModuleNotExistsException):
            prj_mgr.remove_user_module(prjs[0].name, module_to_remove.name)


def test_add_module(modules_data: tuple[CTFManager, Path, list[Project], list[User]]):
    ctf_mgr, _, prjs, usrs = modules_data
    prj_mgr = ctf_mgr.prj_mgr
    user_config_mgr = ctf_mgr.user_config_mgr

    user_compose_path = (
        Path(prjs[0].config_root_dir) / f"{usrs[1].username}_compose.yaml"
    )
    assert user_compose_path.exists()
    with open(user_compose_path, "r") as f:
        data = yaml.safe_load(f)
        services = list(data["services"].keys())
        assert len(services) == 2 and all(
            [i in services for i in {"login", "prj1_module1"}]
        )

    module_name = "new_module"
    uc = user_config_mgr.get_user_config(prjs[0], usrs[1])
    assert uc.modules.get(module_name, None) is None

    module = prj_mgr.create_user_module(prjs[0].name, module_name)
    user_config_mgr.add_module(usrs[1], prjs[0], module)
    uc = user_config_mgr.get_user_config(prjs[0], usrs[1])
    assert uc.modules.get(module_name) is not None

    with open(user_compose_path, "r") as f:
        data = yaml.safe_load(f)
        services = list(data["services"].keys())
        assert len(services) == 3 and all(
            [i in services for i in {"login", "prj1_module1", module_name}]
        )

    with pytest.raises(ModuleExistsException):
        user_config_mgr.add_module(usrs[1], prjs[0], module)


def test_remove_module(
    modules_data: tuple[CTFManager, Path, list[Project], list[User]]
):
    ctf_mgr, _, prjs, usrs = modules_data
    prj_mgr = ctf_mgr.prj_mgr
    user_config_mgr = ctf_mgr.user_config_mgr

    _root_dir = Path(prjs[0].config_root_dir)

    u_modules = prj_mgr.list_user_modules(prjs[0].name)
    uc = user_config_mgr.get_user_config(prjs[0], usrs[2])
    compose_file = _root_dir / f"{usrs[2].username}_compose.yaml"
    assert compose_file.exists()
    modules = list(uc.modules.keys())

    with open(compose_file, "r") as f:
        data = yaml.safe_load(f)
        services = list(data["services"].keys())
        services.remove("login")
        assert set(services) == set(modules)

    module_to_remove = u_modules.pop(0)
    user_config_mgr.remove_module(usrs[2], prjs[0], module_to_remove.name)
    uc = user_config_mgr.get_user_config(prjs[0], usrs[2])
    assert len(uc.modules) == 1 and module_to_remove.name not in uc.modules

    with open(compose_file, "r") as f:
        data = yaml.safe_load(f)
        services = list(data["services"].keys())
        services.remove("login")
        assert module_to_remove.name not in services
