from __future__ import annotations

import subprocess
from typing import Any

from fit_ctf_utils.container_client.base_container_client import BaseContainerClient


class MockClient(BaseContainerClient):

    @classmethod
    def get_images(cls, contains: str | list[str] | None = None) -> list[str]:
        # TODO:
        return []

    @classmethod
    def get_networks(cls, contains: str | list[str] | None = None) -> list[str]:
        # TODO:
        return []

    @classmethod
    def rm_images(cls, contains: str) -> subprocess.CompletedProcess | None:
        # TODO:
        return None

    @classmethod
    def rm_networks(cls, contains: str) -> subprocess.CompletedProcess | None:
        # TODO:
        return None

    @classmethod
    def compose_up(cls, file: str) -> subprocess.CompletedProcess:
        # TODO:
        return subprocess.CompletedProcess(args=["compose", "up"], returncode=0)

    @classmethod
    def compose_down(cls, file: str) -> subprocess.CompletedProcess:
        # TODO:
        return subprocess.CompletedProcess(args=["compose", "down"], returncode=0)

    @classmethod
    def compose_ps(cls, file: str) -> list[str]:
        # TODO:
        return []

    @classmethod
    def compose_ps_json(cls, file: str) -> dict[str, Any]:
        # TODO:
        return {}

    @classmethod
    def compose_build(cls, file: str) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(args=["compose", "build"], returncode=0)

    @classmethod
    def compose_shell(
        cls, file: str, service: str, command: str
    ) -> subprocess.CompletedProcess:
        # TODO:
        return subprocess.CompletedProcess(
            args=["compose", "exec", "bash"], returncode=0
        )

    @classmethod
    def stats(cls, project_name: str) -> list[dict[str, str]]:
        # TODO:
        return []

    @classmethod
    def ps(cls, project_name: str) -> list[str]:
        # TODO:
        return []

    @classmethod
    def ps_json(cls, project_name: str) -> dict[str, Any]:
        # TODO:
        return {}
