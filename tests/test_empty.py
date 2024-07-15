from pathlib import Path

from fit_ctf_backend.ctf_manager import CTFManager
from fit_ctf_db_models.project import Project
from fit_ctf_db_models.user import User


def test_empty(empty_data: tuple[CTFManager, Path, list[Project], list[User]]):
    ctf_mgr, _, _, _ = empty_data
    assert ctf_mgr
    assert len(ctf_mgr.prj_mgr.get_docs()) == 0
    assert len(ctf_mgr.user_mgr.get_docs()) == 0
    assert len(ctf_mgr.user_config_mgr.get_docs()) == 0
