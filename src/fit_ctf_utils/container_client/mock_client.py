from __future__ import annotations

import subprocess
from logging import Logger
from pathlib import Path
from typing import Any

from fit_ctf_utils.container_client.base_container_client import BaseContainerClient


class MockClient(BaseContainerClient):

    @classmethod
    def get_images(
        cls, contains: str | list[str] | None = None
    ) -> list[str]:  # pragma: no cover
        return []

    @classmethod
    def get_networks(
        cls, contains: str | list[str] | None = None
    ) -> list[str]:  # pragma: no cover
        return []

    @classmethod
    def rm_images(
        cls, logger: Logger, contains: str, to_stdout: bool = False
    ) -> int:  # pragma: no cover
        return 0

    @classmethod
    def rm_multiple_images(
        cls, logger: Logger, image_names: list[str], to_stdout: bool = False
    ) -> int:  # pragma: no cover
        return 0

    @classmethod
    def rm_networks(
        cls, logger: Logger, contains: str, to_stdout: bool = False
    ) -> int:  # pragma: no cover
        return 0

    @classmethod
    def rm_multiple_networks(
        cls, logger: Logger, network_names: list[str], to_stdout: bool = False
    ) -> int:  # pragma: no cover
        return 0

    @classmethod
    def compose_up(
        cls, logger: Logger, file: str | Path, to_stdout: bool = False
    ) -> int:  # pragma: no cover
        return 0

    @classmethod
    def compose_down(
        cls, logger: Logger, file: str | Path, to_stdout: bool = False
    ) -> int:  # pragma: no cover
        return 0

    @classmethod
    def compose_ps(cls, file: str | Path) -> list[str]:  # pragma: no cover
        return []

    @classmethod
    def compose_ps_json(
        cls, file: str | Path
    ) -> list[dict[str, Any]]:  # pragma: no cover
        return []

    @classmethod
    def compose_build(
        cls, logger: Logger, file: str | Path, to_stdout: bool = False
    ) -> int:  # pragma: no cover
        return 0

    @classmethod
    def compose_shell(
        cls, file: str | Path, service: str, command: str
    ) -> subprocess.CompletedProcess:  # pragma: no cover
        return subprocess.CompletedProcess(
            args=["compose", "exec", "bash"], returncode=0
        )

    @classmethod
    def stats(cls, project_name: str) -> list[dict[str, str]]:  # pragma: no cover
        return []

    @classmethod
    def ps(cls, project_name: str) -> list[str]:  # pragma: no cover
        return []

    @classmethod
    def ps_json(cls, project_name: str) -> list[dict[str, Any]]:  # pragma: no cover
        return []
