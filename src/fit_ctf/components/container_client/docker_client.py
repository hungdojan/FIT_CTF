import asyncio
import json
import pathlib
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

import fit_ctf.components.container_client.container_client_interface as c_client
from fit_ctf.components.exceptions import CTFComponentException
from fit_ctf.components.types import ErrorCode, HealthCheckDict, TaskSuccess


def _docker_compose_prefix(files: list[Path]) -> list[str]:
    """Build ``docker compose`` argv with one ``-f`` per file (paths/spaces/format-safe)."""
    parts: list[str] = ["docker", "compose"]
    for f in files:
        parts.extend(["-f", str(f.resolve())])
    return parts


def _decode_compose_ps_json(stdout: bytes) -> list[dict[str, Any]]:
    """Parse ``docker compose ps --format json`` (single JSON array or one object per line)."""
    text = stdout.decode().strip()
    if not text:
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        out: list[dict[str, Any]] = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise CTFComponentException(
                    f"`docker compose ps` returned unexpected output: {text[:300]}"
                ) from exc
        return out
    return data if isinstance(data, list) else [data]


def _compose_ps_row_name(row: dict[str, Any]) -> str:
    """Container display name from a compose ``ps --format json`` row (schema varies by version)."""
    names = row.get("Names")
    if isinstance(names, list) and names:
        first = names[0]
        return first if isinstance(first, str) else str(first)
    if isinstance(names, str):
        return names
    n = row.get("Name")
    return str(n) if n is not None else ""


class DockerClient(c_client.ContainerClientInterface):
    def generate_container_prefix(self, *names: str) -> str:
        return f"{'_'.join(names)}-"

    async def get_images(self, contains: str | list[str] | None = None) -> list[str]:
        cmd = ["docker", "images", "--format", '"{{ .Repository }}"']
        return await self._process_get_commands(cmd, contains)

    def create_networks(
        self, logger_name: str, network_names: list[str], to_stdout: bool = False
    ) -> ErrorCode:
        cmd = ["docker", "network", "create"] + network_names
        return self._run_logged_sync(cmd, logger_name, to_stdout=to_stdout)

    async def get_networks(self, contains: str | list[str] | None = None) -> list[str]:
        cmd = ["docker", "network", "ls", "--format", '"{{ .Name }}"']
        return await self._process_get_commands(cmd, contains)

    def rm_network(self, logger_name: str, name: str, to_stdout: bool = False) -> ErrorCode:
        cmd = ["docker", "network", "rm", name]
        return self._run_logged_sync(cmd, logger_name, to_stdout=to_stdout)

    async def rm_images(
        self, logger_name: str, contains: str | list[str], to_stdout: bool = False
    ) -> ErrorCode:
        images = await self.get_images(contains)
        if not images:
            return -1
        cmd = ["docker", "rmi"] + images
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
        )
        await self._process_logging(proc, logger_name=logger_name, to_stdout=to_stdout)
        await proc.wait()
        return proc.returncode if proc.returncode is not None else 255

    async def rm_networks(
        self, logger_name: str, contains: str | list[str], to_stdout: bool = False
    ) -> ErrorCode:
        network_names = await self.get_networks(contains)
        if not network_names:
            return -1
        cmd = ["docker", "network", "rm"] + network_names
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
        )
        await self._process_logging(proc, logger_name=logger_name, to_stdout=to_stdout)
        await proc.wait()
        return proc.returncode if proc.returncode is not None else 255

    async def compose_up(
        self, logger_name: str, files: list[Path], to_stdout: bool = False
    ) -> ErrorCode:
        if not files:
            return 1
        cmd = _docker_compose_prefix(files) + ["up", "-d"]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        await self._process_logging(proc, logger_name=logger_name, to_stdout=to_stdout)
        await proc.wait()
        return proc.returncode if proc.returncode is not None else 255

    async def compose_down(
        self, logger_name: str, files: list[Path], to_stdout: bool = False
    ) -> tuple[ErrorCode, TaskSuccess]:
        if not files:
            return 0, True
        # Do not use check_output: ``ps -q`` exits 1 on compose validation errors or
        # other docker failures; shutdown must not raise CalledProcessError.
        ps = subprocess.run(
            _docker_compose_prefix(files) + ["ps", "-q"],
            capture_output=True,
            text=True,
        )
        if ps.returncode == 0 and not (ps.stdout or "").strip():
            return 0, False
        cmd = _docker_compose_prefix(files) + ["down"]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        await self._process_logging(proc, logger_name=logger_name, to_stdout=to_stdout)
        await proc.wait()
        if proc.returncode is None:
            return 255, False
        if proc.returncode:
            return proc.returncode, False
        # return code 0 means correct clear
        return proc.returncode, not proc.returncode

    async def compose_ps(self, files: list[Path]) -> list[str]:
        files = self._existing_files(files)
        if not files:
            return []
        cmd = _docker_compose_prefix(files) + ["ps", "--format", "{{.Names}}"]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await proc.communicate()
        return [line.strip().strip('"') for line in stdout.decode().splitlines() if line.strip()]

    async def compose_ps_json(self, files: list[Path]) -> list[dict[str, Any]]:
        files = self._existing_files(files)
        if not files:
            return []
        cmd = _docker_compose_prefix(files) + ["ps", "--format", "json"]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await proc.communicate()
        return _decode_compose_ps_json(stdout)

    async def compose_build(
        self, logger_name: str, files: list[Path], to_stdout: bool = False
    ) -> ErrorCode:
        if not files:
            return 1
        cmd = _docker_compose_prefix(files) + ["build"]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        await self._process_logging(proc, logger_name=logger_name, to_stdout=to_stdout)
        await proc.wait()
        return proc.returncode if proc.returncode is not None else 255

    async def compose_logs(
        self,
        logger_name: str,
        files: list[Path],
        *,
        tail: int = 500,
        service: str | None = None,
        to_stdout: bool = True,
    ) -> ErrorCode:
        if not files:
            return 1
        cmd = _docker_compose_prefix(files) + ["logs", "--no-color", f"--tail={tail}"]
        if service:
            cmd.append(service)
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        await self._process_logging(proc, logger_name=logger_name, to_stdout=to_stdout)
        await proc.wait()
        return proc.returncode if proc.returncode is not None else 255

    async def compose_logs_text(
        self,
        files: list[Path],
        *,
        tail: int = 500,
        service: str | None = None,
    ) -> str:
        files = self._existing_files(files)
        if not files:
            return ""
        cmd = _docker_compose_prefix(files) + ["logs", "--no-color", f"--tail={tail}"]
        if service:
            cmd.append(service)
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await proc.communicate()
        return stdout.decode(errors="replace")

    def compose_shell(
        self, files: list[Path], service: str, command: str
    ) -> subprocess.CompletedProcess:  # pragma: no cover
        if not files:
            raise ValueError()
        cmd = _docker_compose_prefix(files) + ["exec", service, command]
        return subprocess.run(cmd, stdout=sys.stdout, stderr=sys.stderr)

    async def stats(self, project_name: str) -> list[dict[str, str]]:
        cmd = [
            "docker",
            "stats",
            "--no-stream",
            "--format",
            # "table {{.Name}} {{.CPUPerc}} {{.MemUsage}} {{.UpTime}}",
            "json",
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
        )
        stdout, _ = await proc.communicate()
        data = self._parse_json_output("docker stats", proc.returncode, stdout)
        return [d for d in data if d["name"].startswith(project_name)]

    async def ps(self, project_name: str) -> list[str]:
        cmd = [
            "docker",
            "ps",
            "-a",
            "--format",
            "table {{.Names}} {{.Networks}} {{.Ports}} {{.State}} {{.CreatedHuman}}",
            f"--filter=name=^{project_name}",
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
        )
        stdout, _ = await proc.communicate()
        return [data.strip('"') for data in stdout.decode().rsplit("\n") if data]

    async def ps_json(self, project_name: str) -> list[dict[str, Any]]:
        cmd = [
            "docker",
            "ps",
            "-a",
            "--format",
            "json",
            f"--filter=name=^{project_name}",
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
        )
        stdout, _ = await proc.communicate()
        data = self._parse_json_output("docker ps", proc.returncode, stdout)
        return data

    async def ps_csv(self, project_name: str, output_file: pathlib.Path):
        cmd = [
            "docker",
            "ps",
            "-a",
            "--no-trunc",
            "--format",
            'table "{{.Names}}","{{.Networks}}","{{.Ports}}","{{.State}}","{{.CreatedHuman}}"',
            f"--filter=name=^{project_name}",
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
        )
        stdout, _ = await proc.communicate()
        # TODO: print to file
        print([data.strip('"') for data in stdout.decode().rsplit("\n") if data])

    async def compose_states(self, files: list[Path]) -> list[HealthCheckDict]:  # pragma: no cover
        files = self._existing_files(files)
        if not files:
            return []
        cmd = _docker_compose_prefix(files) + ["ps", "--format", "json"]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await proc.communicate()
        data = _decode_compose_ps_json(stdout)
        return [
            {
                "name": _compose_ps_row_name(service),
                "state": str(service.get("State", "")),
                "image": str(service.get("Image", "")),
            }
            for service in data
        ]

    async def project_stats(self, project_name: str) -> list[dict]:
        cmd = [
            "docker",
            "ps",
            "-a",
            "--format",
            "json",
            "--filter",
            f"label=project={project_name}",
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
        )
        stdout, _ = await proc.communicate()
        data = self._parse_json_output("docker ps", proc.returncode, stdout)
        return data

    async def build_image(
        self,
        logger_name: str,
        context_path: Path,
        image_name: str,
        containerfile: str = "Containerfile",
        to_stdout: bool = False,
    ) -> ErrorCode:
        """Build a container image from a Containerfile/Dockerfile.

        :param logger_name: Logger name for output
        :type logger_name: str
        :param context_path: Path to build context directory
        :type context_path: Path
        :param image_name: Name to tag the built image
        :type image_name: str
        :param containerfile: Name of Containerfile/Dockerfile (default: "Containerfile")
        :type containerfile: str
        :param to_stdout: Pipe output to stdout as well
        :type to_stdout: bool
        :return: An exit code
        :rtype: ErrorCode
        """
        cmd = [
            "docker",
            "build",
            "-t",
            image_name,
            "-f",
            str(context_path / containerfile),
            str(context_path),
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        await self._process_logging(proc, logger_name=logger_name, to_stdout=to_stdout)
        await proc.wait()
        return proc.returncode if proc.returncode is not None else 255

    async def build_image_stream(
        self,
        context_path: Path,
        image_name: str,
        on_line: Callable[[str], None],
        containerfile: str = "Containerfile",
    ) -> ErrorCode:
        cmd = [
            "docker",
            "build",
            "-t",
            image_name,
            "-f",
            str(context_path / containerfile),
            str(context_path),
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        if proc.stdout is not None:
            while True:
                raw_line = await proc.stdout.readline()
                if not raw_line:
                    break
                on_line(raw_line.decode(errors="replace").rstrip("\n"))
        await proc.wait()
        return proc.returncode if proc.returncode is not None else 255

    async def build_image_text(
        self,
        context_path: Path,
        image_name: str,
        containerfile: str = "Containerfile",
    ) -> tuple[ErrorCode, str]:
        cmd = [
            "docker",
            "build",
            "-t",
            image_name,
            "-f",
            str(context_path / containerfile),
            str(context_path),
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await proc.communicate()
        code = proc.returncode if proc.returncode is not None else 255
        return code, stdout.decode(errors="replace")
