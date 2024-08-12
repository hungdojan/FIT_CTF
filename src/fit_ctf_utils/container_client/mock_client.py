from __future__ import annotations

import subprocess
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
        cls, contains: str
    ) -> subprocess.CompletedProcess | None:  # pragma: no cover
        return None

    @classmethod
    def rm_networks(
        cls, contains: str
    ) -> subprocess.CompletedProcess | None:  # pragma: no cover
        return None

    @classmethod
    def compose_up(
        cls, file: str | Path
    ) -> subprocess.CompletedProcess:  # pragma: no cover
        return subprocess.CompletedProcess(args=["compose", "up"], returncode=0)

    @classmethod
    def compose_down(
        cls, file: str | Path
    ) -> subprocess.CompletedProcess:  # pragma: no cover
        return subprocess.CompletedProcess(args=["compose", "down"], returncode=0)

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
        cls, file: str | Path
    ) -> subprocess.CompletedProcess:  # pragma: no cover
        return subprocess.CompletedProcess(args=["compose", "build"], returncode=0)

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
