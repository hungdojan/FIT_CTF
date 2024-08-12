from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

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
    def rm_images(cls, contains: str) -> subprocess.CompletedProcess | None:
        images = cls.get_images(contains)
        if not images:
            return
        cmd = ["podman", "rmi"] + images
        return subprocess.run(cmd, stdout=sys.stdout, stderr=sys.stderr)

    @classmethod
    def rm_networks(cls, contains: str) -> subprocess.CompletedProcess | None:
        network_names = cls.get_networks(contains)
        if not network_names:
            return
        cmd = ["podman", "network", "rm"] + network_names
        return subprocess.run(cmd, stdout=sys.stdout, stderr=sys.stderr)

    @classmethod
    def compose_up(cls, file: str | Path) -> subprocess.CompletedProcess:
        # TODO: eliminate whitespaces
        cmd = f"podman-compose -f {file} up -d"
        # TODO redirect outputs; store to log file
        proc = subprocess.run(
            cmd.split(),
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
        return proc

    @classmethod
    def compose_down(cls, file: str | Path) -> subprocess.CompletedProcess:
        if len(cls.compose_ps(file)) == 0:
            return subprocess.CompletedProcess(
                args=["podman-compose", "down"], returncode=0
            )
        # TODO: eliminate whitespaces
        cmd = f"podman-compose -f {file} down"
        # TODO: redirect outputs
        proc = subprocess.run(
            cmd.split(),
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
        return proc

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
    def compose_build(cls, file: str | Path) -> subprocess.CompletedProcess:
        cmd = f"podman-compose -f {file} build"
        # TODO: redirect outputs
        proc = subprocess.run(
            cmd.split(),
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
        return proc

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
        proc = subprocess.run(cmd, capture_output=True, text=True)
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
