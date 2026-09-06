from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fit_ctf.components.container_client.podman_client import PodmanClient


@pytest.fixture
def podman_client() -> PodmanClient:
    return PodmanClient(MagicMock())


class _FakeProc:
    def __init__(self, stdout: bytes):
        self.stdout = stdout

    async def communicate(self):
        return self.stdout, b""


@pytest.fixture
def compose_file(tmp_path: Path) -> Path:
    # compose_ps filters out non-existent files, so the fixture must be real
    path = tmp_path / "scenario_compose.yaml"
    path.write_text("services: {}\n")
    return path


@pytest.mark.asyncio
async def test_compose_ps_empty_when_no_containers(podman_client: PodmanClient, compose_file: Path):
    with patch(
        "fit_ctf.components.container_client.podman_client.asyncio.create_subprocess_shell",
        new=AsyncMock(return_value=_FakeProc(b"")),
    ) as mock_shell:
        result = await podman_client.compose_ps([compose_file])

        assert result == []
        assert "ps -q" in mock_shell.await_args.args[0]


@pytest.mark.asyncio
async def test_compose_ps_returns_container_ids(podman_client: PodmanClient, compose_file: Path):
    stdout = b"1a6bde9eeb5b\nf4053947c8c1\n"
    with patch(
        "fit_ctf.components.container_client.podman_client.asyncio.create_subprocess_shell",
        new=AsyncMock(return_value=_FakeProc(stdout)),
    ):
        result = await podman_client.compose_ps([compose_file])

        assert result == ["1a6bde9eeb5b", "f4053947c8c1"]


@pytest.mark.asyncio
async def test_compose_ps_empty_files(podman_client: PodmanClient):
    assert await podman_client.compose_ps([]) == []


@pytest.mark.asyncio
async def test_compose_ps_missing_file_means_not_running(podman_client: PodmanClient):
    assert await podman_client.compose_ps([Path("/nonexistent/scenario_compose.yaml")]) == []
