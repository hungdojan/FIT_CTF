from tests import FixtureData


def test_empty(empty_data: FixtureData):
    ctf_mgr, _ = empty_data
    assert ctf_mgr
    assert len(ctf_mgr.prj_mgr.get_docs()) == 0
    assert len(ctf_mgr.user_mgr.get_docs()) == 0
    assert len(ctf_mgr.user_enrollment_mgr.get_docs()) == 0


def test_file_structure(empty_data: FixtureData):
    _, paths = empty_data
    share_path = paths / "share"
    assert (share_path / "project").exists() and (share_path / "project").is_dir()
    assert (share_path / "user").exists() and (share_path / "user").is_dir()
    assert (share_path / "module").exists() and (share_path / "module").is_dir()
