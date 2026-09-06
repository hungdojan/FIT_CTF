"""Regression tests: container-runtime failures must surface, never vanish.

Covers the "Health button does nothing" report: with podman missing (or a
stopped cluster producing non-JSON/empty ps output) the JSON parse failure was
swallowed silently by the UI worker.
"""

from unittest.mock import MagicMock, patch

import pytest

from fit_ctf.components.container_client.podman_client import PodmanClient
from fit_ctf.components.exceptions import CTFComponentException
from fit_ctf_admin.core.live_gateway import LiveGateway
from fit_ctf_admin.exceptions import AdminError
from tests import FixtureData


class _FakeProc:
    def __init__(self, stdout: bytes, returncode: int = 0) -> None:
        self._stdout = stdout
        self.returncode = returncode

    async def communicate(self):
        return self._stdout, b""


def _patched_shell(stdout: bytes, returncode: int = 0):
    return patch(
        "fit_ctf.components.container_client.podman_client.asyncio.create_subprocess_shell",
        return_value=_FakeProc(stdout, returncode),
    )


@pytest.fixture
def client() -> PodmanClient:
    return PodmanClient(MagicMock())


class TestComposeStatesParsing:
    async def test_empty_output_means_no_containers(self, client):
        with _patched_shell(b"", returncode=0):
            assert await client.compose_states([MagicMock()]) == []

    async def test_command_not_found_raises_readable_error(self, client):
        with _patched_shell(b"/bin/sh: podman-compose: command not found\n", returncode=127):
            with pytest.raises(CTFComponentException) as excinfo:
                await client.compose_states([MagicMock()])
        message = str(excinfo.value)
        assert "exit 127" in message and "command not found" in message

    async def test_garbage_output_raises_readable_error(self, client):
        with _patched_shell(b"not json at all", returncode=0):
            with pytest.raises(CTFComponentException) as excinfo:
                await client.compose_states([MagicMock()])
        assert "unexpected output" in str(excinfo.value)

    async def test_valid_json_is_parsed(self, client):
        payload = b'[{"Names": ["prj_web"], "State": "running", "Image": "fit-ctf/web"}]'
        with _patched_shell(payload, returncode=0):
            rows = await client.compose_states([MagicMock()])
        assert rows == [{"name": "prj_web", "state": "running", "image": "fit-ctf/web"}]


class TestGatewaySurfacesRuntimeErrors:
    async def test_missing_runtime_becomes_admin_error(self, connected_data: FixtureData):
        gateway = LiveGateway(connected_data[0])
        ctf_app = connected_data[0]

        async def _boom(files):
            raise FileNotFoundError(2, "No such file or directory", "podman-compose")

        with patch.object(ctf_app.project_cluster_mgr.c_client, "compose_states", _boom):
            with pytest.raises(AdminError) as excinfo:
                await gateway.project_cluster_health("prj1")
        message = str(excinfo.value)
        assert "podman-compose" in message and "PATH" in message

    async def test_unexpected_exception_becomes_admin_error(self, connected_data: FixtureData):
        gateway = LiveGateway(connected_data[0])
        ctf_app = connected_data[0]

        async def _boom(files):
            raise RuntimeError("kaboom")

        with patch.object(ctf_app.project_cluster_mgr.c_client, "compose_states", _boom):
            with pytest.raises(AdminError) as excinfo:
                await gateway.project_cluster_health("prj1")
        assert "kaboom" in str(excinfo.value)

    async def test_component_exception_becomes_admin_error(self, connected_data: FixtureData):
        gateway = LiveGateway(connected_data[0])
        ctf_app = connected_data[0]

        async def _boom(files):
            raise CTFComponentException("`podman-compose ps` failed (exit 127): not found")

        with patch.object(ctf_app.project_cluster_mgr.c_client, "compose_states", _boom):
            with pytest.raises(AdminError) as excinfo:
                await gateway.project_cluster_health("prj1")
        assert "exit 127" in str(excinfo.value)


class TestMissingComposeFiles:
    """Read-only compose ops must not invoke the engine without any -f flag."""

    async def test_no_files_returns_empty_without_subprocess(self, client):
        with _patched_shell(b"", returncode=0) as mock_shell:
            assert await client.compose_states([]) == []
            assert await client.compose_ps([]) == []
            assert await client.compose_ps_json([]) == []
            assert await client.compose_logs_text([]) == ""
        mock_shell.assert_not_called()

    async def test_missing_files_are_filtered_out(self, client, tmp_path):
        ghost = tmp_path / "not_compiled" / "scenario_compose.yaml"
        with _patched_shell(b"", returncode=0) as mock_shell:
            assert await client.compose_states([ghost]) == []
            assert await client.compose_logs_text([ghost]) == ""
        mock_shell.assert_not_called()

    async def test_existing_file_is_used(self, client, tmp_path):
        real = tmp_path / "scenario_compose.yaml"
        real.write_text("services: {}\n")
        with _patched_shell(b"[]", returncode=0) as mock_shell:
            assert await client.compose_states([real]) == []
        mock_shell.assert_called_once()
