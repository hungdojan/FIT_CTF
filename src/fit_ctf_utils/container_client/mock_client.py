from __future__ import annotations

import subprocess

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
    def stats(cls, project_name: str) -> subprocess.CompletedProcess:
        # TODO:
        return subprocess.CompletedProcess(args=["stats"], returncode=0)

    @classmethod
    def ps(cls, project_name: str) -> subprocess.CompletedProcess:
        # TODO:
        return subprocess.CompletedProcess(args=["ps", "-a"], returncode=0)

    @classmethod
    def shell(
        cls, file: str, service: str, command: str
    ) -> subprocess.CompletedProcess:
        # TODO:
        return subprocess.CompletedProcess(
            args=["compose", "exec", "bash"], returncode=0
        )
