import subprocess
from pathlib import Path
from typing import Any

import fit_ctf.components.container_client.container_client_interface as c_client
from fit_ctf.components.types import ErrorCode, HealthCheckDict, TaskSuccess


class MockClient(c_client.ContainerClientInterface):
    def generate_container_prefix(self, *names: str) -> str:
        return ""

    async def get_images(
        self, contains: str | list[str] | None = None
    ) -> list[str]:  # pragma: no cover
        return []

    def create_networks(
        self, logger_name: str, network_names: list[str], to_stdout: bool = False
    ) -> ErrorCode:  # pragma: no cover
        return 0

    async def get_networks(
        self, contains: str | list[str] | None = None
    ) -> list[str]:  # pragma: no cover
        return []

    def rm_network(
        self, logger_name: str, name: str, to_stdout: bool = False
    ) -> ErrorCode:  # pragma: no cover
        return 0

    async def rm_images(
        self, logger_name: str, contains: str | list[str], to_stdout: bool = False
    ) -> ErrorCode:  # pragma: no cover
        return 0

    async def rm_networks(
        self, logger_name: str, contains: str | list[str], to_stdout: bool = False
    ) -> ErrorCode:  # pragma: no cover
        return 0

    async def compose_up(
        self, logger_name: str, files: list[Path], to_stdout: bool = False
    ) -> ErrorCode:  # pragma: no cover
        return 0

    async def compose_down(
        self, logger_name: str, files: list[Path], to_stdout: bool = False
    ) -> tuple[ErrorCode, TaskSuccess]:  # pragma: no cover
        return 0, True

    async def compose_ps(self, files: list[Path]) -> list[str]:  # pragma: no cover
        return []

    async def compose_ps_json(self, files: list[Path]) -> list[dict[str, Any]]:  # pragma: no cover
        return []

    async def compose_build(
        self, logger_name: str, files: list[Path], to_stdout: bool = False
    ) -> ErrorCode:  # pragma: no cover
        return 0

    async def compose_logs(
        self,
        logger_name: str,
        files: list[Path],
        *,
        tail: int = 500,
        service: str | None = None,
        to_stdout: bool = True,
    ) -> ErrorCode:  # pragma: no cover
        return 0

    async def compose_logs_text(
        self,
        files: list[Path],
        *,
        tail: int = 500,
        service: str | None = None,
    ) -> str:  # pragma: no cover
        return ""

    def compose_shell(
        self, files: list[Path], service: str, command: str
    ) -> subprocess.CompletedProcess:  # pragma: no cover
        return subprocess.CompletedProcess(args=["compose", "exec", "bash"], returncode=0)

    async def stats(self, project_name: str) -> list[dict[str, str]]:  # pragma: no cover
        return []

    async def ps(self, project_name: str) -> list[str]:  # pragma: no cover
        return []

    async def ps_json(self, project_name: str) -> list[dict[str, Any]]:  # pragma: no cover
        return []

    async def ps_csv(self, project_name: str, output_file: Path):
        return

    async def project_stats(self, project_name: str) -> list[dict]:  # pragma: no cover
        return []

    async def build_image(
        self,
        logger_name: str,
        context_path: Path,
        image_name: str,
        containerfile: str = "Containerfile",
        to_stdout: bool = False,
    ) -> ErrorCode:  # pragma: no cover
        return 0

    async def build_image_text(
        self,
        context_path: Path,
        image_name: str,
        containerfile: str = "Containerfile",
    ) -> tuple[ErrorCode, str]:  # pragma: no cover
        return 0, ""

    async def compose_states(self, files: list[Path]) -> list[HealthCheckDict]:
        return []
