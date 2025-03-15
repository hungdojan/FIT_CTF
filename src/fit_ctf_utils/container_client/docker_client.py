import json
import pathlib
import subprocess
import sys
from logging import Logger
from pathlib import Path
from typing import Any

from fit_ctf_utils.container_client.container_client_interface import (
    ContainerClientInterface,
)
from fit_ctf_utils.types import HealthCheckDict


class DockerClient(ContainerClientInterface):

    @classmethod
    def generate_container_prefix(cls, *names: str) -> str:
        return f"{'_'.join(names)}-"

    @classmethod
    def get_images(cls, contains: str | list[str] | None = None) -> list[str]:
        cmd = ["docker", "images", "--format", '"{{ .Repository }}"']
        return cls._process_get_commands(cmd, contains)

    @classmethod
    def get_networks(cls, contains: str | list[str] | None = None) -> list[str]:
        cmd = ["docker", "network", "ls", "--format", '"{{ .Name }}"']
        return cls._process_get_commands(cmd, contains)

    @classmethod
    def rm_images(
        cls, logger: Logger, contains: str | list[str], to_stdout: bool = False
    ) -> int:
        images = cls.get_images(contains)
        if not images:
            return -1
        cmd = ["docker", "rmi"] + images
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        cls._process_logging(logger, proc.stdout.decode(), to_stdout)
        return proc.returncode

    @classmethod
    def rm_networks(
        cls, logger: Logger, contains: str | list[str], to_stdout: bool = False
    ) -> int:
        network_names = cls.get_networks(contains)
        if not network_names:
            return -1
        cmd = ["docker", "network", "rm"] + network_names
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        cls._process_logging(logger, proc.stdout.decode(), to_stdout)
        return proc.returncode

    @classmethod
    def compose_up(
        cls, logger: Logger, file: str | Path, to_stdout: bool = False
    ) -> int:
        # TODO: eliminate whitespaces
        if isinstance(file, Path):
            file = str(file.resolve())
        cmd = f"docker compose -f {file} up -d"
        proc = subprocess.run(
            cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
        cls._process_logging(logger, proc.stdout.decode(), to_stdout)
        return proc.returncode

    @classmethod
    def compose_down(
        cls, logger: Logger, file: str | Path, to_stdout: bool = False
    ) -> int:
        if isinstance(file, Path):
            file = str(file.resolve())
        res = subprocess.check_output(
            ["docker compose", "-f", file, "ps", "-q"], text=True
        )
        if not res.strip():
            return 0
        proc = subprocess.run(
            ["docker compose", "-f", file, "down"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        cls._process_logging(logger, proc.stdout.decode(), to_stdout)
        return proc.returncode

    @classmethod
    def compose_ps(cls, file: str | Path) -> list[str]:
        if isinstance(file, Path):
            file = str(file.resolve())
        cmd = ["docker", "compose", "-f", file, "ps", "--format", '"{{ .Names }}"']
        proc = subprocess.run(cmd, capture_output=True, text=True)
        return [data.strip('"') for data in proc.stdout.rsplit()]

    @classmethod
    def compose_ps_json(cls, file: str | Path) -> list[dict[str, Any]]:
        if isinstance(file, Path):
            file = str(file.resolve())
        cmd = ["docker", "compose", "-f", file, "ps", "--format", "json"]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(proc.stdout)
        return data

    @classmethod
    def compose_build(
        cls, logger: Logger, file: str | Path, to_stdout: bool = False
    ) -> int:
        if isinstance(file, Path):
            file = str(file.resolve())
        cmd = f"docker compose -f {file} build"
        proc = subprocess.run(
            cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
        cls._process_logging(logger, proc.stdout.decode(), to_stdout)
        return proc.returncode

    @classmethod
    def compose_shell(
        cls, file: str | Path, service: str, command: str
    ) -> subprocess.CompletedProcess:  # pragma: no cover
        if isinstance(file, Path):
            file = str(file.resolve())
        cmd = f"docker compose -f {file} exec {service} {command}"
        return subprocess.run(cmd.split(), stdout=sys.stdout, stderr=sys.stderr)

    @classmethod
    def stats(cls, project_name: str) -> list[dict[str, str]]:
        cmd = [
            "docker",
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
            "docker",
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
            "docker",
            "ps",
            "-a",
            "--format",
            "json",
            f"--filter=name=^{project_name}",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(proc.stdout)
        return data

    @classmethod
    def ps_csv(cls, project_name: str, output_file: pathlib.Path):
        cmd = [
            "docker",
            "ps",
            "-a",
            "--no-truc" "--format",
            'table "{{.Names}}","{{.Networks}}","{{.Ports}}","{{.State}}","{{.CreatedHuman}}"',
            f"--filter=name=^{project_name}",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        # TODO: print to file
        print([data.strip('"') for data in proc.stdout.rsplit("\n") if data])

    @classmethod
    def compose_states(
        cls, file: str | Path
    ) -> list[HealthCheckDict]:  # pragma: no cover
        if isinstance(file, Path):
            file = str(file.resolve())
        cmd = ["docker", "compose", "-f", file, "ps", "--format", "json"]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(proc.stdout)
        # filtering
        return [
            {
                "name": service["Names"][0],
                "state": service["State"],
                "image": service["Image"],
            }
            for service in data
        ]

    @classmethod
    def project_stats(cls, project_name: str) -> list[dict]:
        cmd = [
            "docker",
            "ps",
            "-a",
            "--format",
            "json",
            "--filter",
            f"label=project={project_name}",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(proc.stdout)
        return data
