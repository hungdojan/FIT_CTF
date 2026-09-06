"""Gateway tests for project export and module file editing (round 4)."""

import zipfile

import pytest

from fit_ctf_admin.core.live_gateway import LiveGateway
from fit_ctf_admin.core.preview_gateway import PreviewGateway
from fit_ctf_admin.core.preview_store import PreviewStore
from fit_ctf_admin.exceptions import AdminError
from tests import FixtureData


class TestExportProject:
    async def test_live_export_writes_zip(self, connected_data: FixtureData, tmp_path):
        gateway = LiveGateway(connected_data[0])
        target = tmp_path / "out" / "prj1_export.zip"
        written = await gateway.export_project("prj1", str(target))
        assert written == str(target.resolve())
        with zipfile.ZipFile(target) as zf:
            assert "database_dump.yaml" in zf.namelist()

    async def test_live_export_unknown_project_raises(self, connected_data: FixtureData, tmp_path):
        gateway = LiveGateway(connected_data[0])
        with pytest.raises(AdminError):
            await gateway.export_project("ghost", str(tmp_path / "x.zip"))

    async def test_live_export_directory_target_raises(self, connected_data: FixtureData, tmp_path):
        gateway = LiveGateway(connected_data[0])
        with pytest.raises(AdminError):
            await gateway.export_project("prj1", str(tmp_path))

    async def test_preview_export_raises(self):
        gateway = PreviewGateway(PreviewStore.with_sample_data())
        with pytest.raises(AdminError):
            await gateway.export_project("intro_linux", "out.zip")


@pytest.fixture(params=["preview", "live"])
def gateway(request):
    if request.param == "preview":
        return PreviewGateway(PreviewStore.with_sample_data())
    ctf_app, _ = request.getfixturevalue("empty_data")
    return LiveGateway(ctf_app)


class TestModuleFiles:
    async def test_list_contains_containerfile(self, gateway):
        files = await gateway.list_module_files("template")
        assert "Containerfile" in files

    async def test_read_edit_roundtrip(self, gateway):
        original = await gateway.read_module_file("template", "Containerfile")
        assert original.strip()
        await gateway.save_module_file("template", "Containerfile", original + "\n# edited\n")
        updated = await gateway.read_module_file("template", "Containerfile")
        assert updated.endswith("# edited\n")

    async def test_missing_file_raises(self, gateway):
        with pytest.raises(AdminError):
            await gateway.read_module_file("template", "nope.txt")

    async def test_unknown_module_raises(self, gateway):
        with pytest.raises(AdminError):
            await gateway.list_module_files("ghost_module")

    async def test_build_returns_success_and_text(self, gateway):
        success, text = await gateway.build_module("template")
        assert success is True
        assert isinstance(text, str) and text


class TestModuleFileTraversal:
    async def test_live_rejects_file_names_outside_module_dir(self, empty_data: FixtureData):
        """The gateway must confine file access to the module directory."""
        gateway = LiveGateway(empty_data[0])
        with pytest.raises(AdminError):
            await gateway.read_module_file("template", "../outside_module.txt")
        with pytest.raises(AdminError):
            await gateway.save_module_file("template", "../outside_module.txt", "x")
