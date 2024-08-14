from __future__ import annotations

import json
import subprocess
import sys
from logging import Logger
from pathlib import Path
from typing import Any

import fit_ctf_utils
from fit_ctf_utils.container_client.base_container_client import BaseContainerClient


class PodmanClient(BaseContainerClient):

    @classmethod
    def get_images(cls, contains: str | list[str] | None = None) -> list[str]:
        cmd = ["podman", "images", "--format", '"{{ .Repository }}"']
        proc = subprocess.run(cmd, capture_output=True, text=True)

        if not contains:
            # TODO: hazardous
            return [data.strip('"') for data in proc.stdout.rsplit()]
        if isinstance(contains, list):
            out = []
            for data in proc.stdout.rsplit():
                data = data.strip('"')
                for user_prj in contains:
                    if user_prj not in data:
                        continue
                    out.append(data)
            return out
        return [data.strip('"') for data in proc.stdout.rsplit() if contains in data]

    @classmethod
    def get_networks(cls, contains: str | list[str] | None = None) -> list[str]:
        cmd = ["podman", "network", "ls", "--format", '"{{.Name}}"']
        proc = subprocess.run(cmd, capture_output=True, text=True)

        if not contains:
            return [data.strip('"') for data in proc.stdout.rsplit()]
        if isinstance(contains, list):
            out = []
            for data in proc.stdout.rsplit():
                data = data.strip('"')
                for user_prj in contains:
                    if user_prj not in data:
                        continue
                    out.append(data)
            return out
        return [data.strip('"') for data in proc.stdout.rsplit() if contains in data]

    @classmethod
    def rm_images(cls, logger: Logger, contains: str, to_stdout: bool = False) -> int:
        images = cls.get_images(contains)
        if not images:
            return -1
        cmd = ["podman", "rmi"] + images
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        message = proc.stdout.decode("utf-8")
        logger.info(message)
        if to_stdout:
            fit_ctf_utils.GLOBAL_LOGGER.info(message)
        return proc.returncode

    @classmethod
    def rm_multiple_images(
        cls, logger: Logger, image_names: list[str], to_stdout: bool = False
    ) -> int:
        cmd = ["podman", "rmi"] + image_names
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        message = proc.stdout.decode("utf-8")
        logger.info(message)
        if to_stdout:
            fit_ctf_utils.GLOBAL_LOGGER.info(message)
        return proc.returncode

    @classmethod
    def rm_networks(cls, logger: Logger, contains: str, to_stdout: bool = False) -> int:
        network_names = cls.get_networks(contains)
        if not network_names:
            return -1
        cmd = ["podman", "network", "rm"] + network_names
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        message = proc.stdout.decode("utf-8")
        logger.info(message)
        if to_stdout:
            fit_ctf_utils.GLOBAL_LOGGER.info(message)
        return proc.returncode

    @classmethod
    def rm_multiple_networks(
        cls, logger: Logger, network_names: list[str], to_stdout: bool = False
    ) -> int:
        cmd = ["podman", "network", "rm"] + network_names
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        message = proc.stdout.decode("utf-8")
        logger.info(message)
        if to_stdout:
            fit_ctf_utils.GLOBAL_LOGGER.info(message)
        return proc.returncode

    @classmethod
    def compose_up(
        cls, logger: Logger, file: str | Path, to_stdout: bool = False
    ) -> int:
        # TODO: eliminate whitespaces
        cmd = f"podman-compose -f {file} up -d"
        proc = subprocess.run(
            cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
        message = proc.stdout.decode("utf-8")
        logger.info(message)
        if to_stdout:
            fit_ctf_utils.GLOBAL_LOGGER.info(message)
        return proc.returncode

    @classmethod
    def compose_down(
        cls, logger: Logger, file: str | Path, to_stdout: bool = False
    ) -> int:
        if len(cls.compose_ps(file)) == 0:
            return 0
        # TODO: eliminate whitespaces
        cmd = f"podman-compose -f {file} down"
        proc = subprocess.run(
            cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
        message = proc.stdout.decode("utf-8")
        logger.info(message)
        if to_stdout:
            fit_ctf_utils.GLOBAL_LOGGER.info(message)
        return proc.returncode

    @classmethod
    def compose_ps(cls, file: str | Path) -> list[str]:
        cmd = ["podman-compose", "-f", file, "ps", "--format", '"{{ .Names }}"']
        proc = subprocess.run(cmd, capture_output=True, text=True)
        return [data.strip('"') for data in proc.stdout.rsplit()]

    @classmethod
    def compose_ps_json(cls, file: str | Path) -> list[dict[str, Any]]:
        cmd = ["podman-compose", "-f", file, "ps", "--format", "json"]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(proc.stdout)
        return data

    @classmethod
    def compose_build(
        cls, logger: Logger, file: str | Path, to_stdout: bool = False
    ) -> int:
        cmd = f"podman-compose -f {file} build"
        proc = subprocess.run(
            cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
        message = proc.stdout.decode("utf-8")
        logger.info(message)
        if to_stdout:
            fit_ctf_utils.GLOBAL_LOGGER.info(message)
        return proc.returncode

    @classmethod
    def compose_shell(
        cls, file: str | Path, service: str, command: str
    ) -> subprocess.CompletedProcess:  # pragma: no cover
        cmd = f"podman-compose -f {file} exec {service} {command}"
        return subprocess.run(cmd.split(), stdout=sys.stdout, stderr=sys.stderr)

    @classmethod
    def stats(cls, project_name: str) -> list[dict[str, str]]:
        cmd = [
            "podman",
            "stats",
            "--no-stream",
            "--format",
            # "table {{.Name}} {{.CPUPerc}} {{.MemUsage}} {{.UpTime}}",
            "json",
        ]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        data = json.loads(proc.stdout)
        return [d for d in data if d["name"].startswith(project_name)]

    @classmethod
    def ps(cls, project_name: str) -> list[str]:
        cmd = [
            "podman",
            "ps",
            "-a",
            "--format",
            "table {{.Names}} {{.Networks}} {{.Ports}} {{.State}} {{.CreatedHuman}}",
            f"--filter=name=^{project_name}",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        return [data.strip('"') for data in proc.stdout.rsplit("\n") if data]

    @classmethod
    def ps_json(cls, project_name: str) -> list[dict[str, Any]]:
        cmd = [
            "podman",
            "ps",
            "-a",
            "--format",
            "json",
            f"--filter=name=^{project_name}",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(proc.stdout)
        return data
