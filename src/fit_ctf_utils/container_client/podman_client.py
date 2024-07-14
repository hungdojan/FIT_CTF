from __future__ import annotations

import subprocess
import sys

from fit_ctf_utils.container_client.base_container_client import BaseContainerClient


class PodmanClient(BaseContainerClient):

    @classmethod
    def get_images(cls, contains: str | list[str] | None = None) -> list[str]:
        cmd = ["podman", "images", "--format", '"{{ .Repository }}"']
        proc = subprocess.run(cmd, capture_output=True, text=True)

        if not contains:
            # TODO: hazardous
            return [data.rstrip('"').lstrip('"') for data in proc.stdout.rsplit()]
        if isinstance(contains, list):
            out = []
            for data in proc.stdout.rsplit():
                data = data.rstrip('"').lstrip('"')
                for user_prj in contains:
                    if user_prj not in data:
                        continue
                    out.append(data)
            return out
        return [
            data.rstrip('"').lstrip('"')
            for data in proc.stdout.rsplit()
            if contains in data
        ]

    @classmethod
    def get_networks(cls, contains: str | list[str] | None = None) -> list[str]:
        cmd = ["podman", "network", "ls", "--format", '"{{.Name}}"']
        proc = subprocess.run(cmd, capture_output=True, text=True)

        if not contains:
            return [data.rstrip('"').lstrip('"') for data in proc.stdout.rsplit()]
        if isinstance(contains, list):
            out = []
            for data in proc.stdout.rsplit():
                data = data.rstrip('"').lstrip('"')
                for user_prj in contains:
                    if user_prj not in data:
                        continue
                    out.append(data)
            return out
        return [
            data.rstrip('"').lstrip('"')
            for data in proc.stdout.rsplit()
            if contains in data
        ]

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
    def compose_up(cls, file: str) -> subprocess.CompletedProcess:
        # TODO: eliminate whitespaces
        cmd = f"podman-compose -f {file} up -d"
        # TODO redirect outputs
        proc = subprocess.run(
            cmd.split(),
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
        return proc

    @classmethod
    def compose_down(cls, file: str) -> subprocess.CompletedProcess:
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
    def compose_ps(cls, file: str) -> list[str]:
        cmd = ["podman-compose", "-f", file, "ps", "--format", '"{{ .Names }}"']
        proc = subprocess.run(cmd, capture_output=True, text=True)
        return [data.lstrip('"').rstrip('"') for data in proc.stdout.rsplit()]

    @classmethod
    def stats(cls, project_name: str) -> subprocess.CompletedProcess:
        cmd = "podman ps -a --format={{.Names}} " f"--filter=name=^{project_name}"
        proc = subprocess.run(cmd.split(), capture_output=True, text=True)

        container_names = [
            data.rstrip('"').lstrip('"') for data in proc.stdout.rsplit()
        ]
        cmd = [
            "podman",
            "stats",
            "--no-stream",
            "--format",
            "table {{.Name}} {{.CPUPerc}} {{.MemUsage}} {{.UpTime}}",
        ] + container_names
        return subprocess.run(cmd, stdout=sys.stdout, stderr=sys.stderr)

    @classmethod
    def ps(cls, project_name: str) -> subprocess.CompletedProcess:
        cmd = [
            "podman",
            "ps",
            "-a",
            "--format",
            "table {{.Names}} {{.Networks}} {{.Ports}} {{.State}} {{.CreatedHuman}}",
            f"--filter=name=^{project_name}",
        ]
        return subprocess.run(cmd, stdout=sys.stdout, stderr=sys.stderr)

    @classmethod
    def shell(
        cls, file: str, service: str, command: str
    ) -> subprocess.CompletedProcess:
        cmd = f"podman-compose -f {file} exec {service} {command}"
        return subprocess.run(cmd.split(), stdout=sys.stdout, stderr=sys.stderr)
