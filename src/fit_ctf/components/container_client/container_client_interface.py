import json
import pathlib
import subprocess
from abc import ABC, abstractmethod
from asyncio.subprocess import Process
from pathlib import Path
from typing import TYPE_CHECKING, Any

import fit_ctf.components.utils
from fit_ctf.components.exceptions import CTFComponentException
from fit_ctf.components.types import ErrorCode, HealthCheckDict, TaskSuccess

if TYPE_CHECKING:
    import fit_ctf.ctf_base as _ctf_base


class ContainerClientInterface(ABC):
    def __init__(self, ctf_base: "_ctf_base.CTFBase") -> None:
        self._ctf_base = ctf_base

    @property
    def ctf_base(self) -> "_ctf_base.CTFBase":
        return self._ctf_base

    async def _process_get_commands(
        self, cmd: list[str], contains: str | list[str] | None = None
    ) -> list[str]:
        _, stdout = await fit_ctf.components.utils.create_async_exec(cmd)

        if not contains:
            # TODO: hazardous
            return [data.strip('"') for data in stdout.decode().rsplit()]
        if isinstance(contains, list):
            out = []
            for data in stdout.decode().rsplit():
                data = data.strip('"')
                for user_prj in contains:
                    if user_prj not in data:
                        continue
                    out.append(data)
            return out
        return [data.strip('"') for data in stdout.decode().rsplit() if contains in data]

    async def _process_logging(self, proc: Process, logger_name: str, to_stdout: bool = False):
        if proc.stdout:
            async for line in proc.stdout:
                message = line.decode().strip()
                self.ctf_base.logger.info(message, logger_name=logger_name)
                if to_stdout:
                    self.ctf_base.logger.print(message)

    def _run_logged_sync(self, cmd: list[str], logger_name: str, *, to_stdout: bool = False) -> int:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        out = proc.stdout or ""
        for line in out.splitlines():
            self.ctf_base.logger.info(line, logger_name=logger_name)
            if to_stdout:
                self.ctf_base.logger.print(line)
        rc = proc.returncode
        return rc if rc is not None else 255

    @staticmethod
    def _existing_files(files: list[Path]) -> list[Path]:
        """Compose files that actually exist on disk.

        Read-only compose operations (ps/states/logs) treat missing compiled
        files as "nothing running": running the engine without any ``-f`` flag
        would print a usage error (e.g. docker's "no configuration file
        provided") instead of an empty listing.
        """
        return [path for path in files if path.exists()]

    @staticmethod
    def _parse_json_output(cmd_label: str, returncode: int | None, stdout: bytes):
        """Decode JSON output of a container command, with readable failures.

        Empty output with a zero exit code means "no containers" and yields an
        empty list. A nonzero exit code (e.g. 127 when the runtime binary is
        missing) or non-JSON output raises :class:`CTFComponentException`
        carrying an output snippet instead of a bare ``JSONDecodeError``.
        """
        text = stdout.decode(errors="replace").strip()
        if returncode not in (0, None):
            raise CTFComponentException(
                f"`{cmd_label}` failed (exit {returncode}): {text[:300] or '(no output)'}"
            )
        if not text:
            return []
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise CTFComponentException(
                f"`{cmd_label}` returned unexpected output: {text[:300]}"
            ) from exc

    @abstractmethod
    def generate_container_prefix(self, *names: str) -> str:
        raise NotImplementedError()

    @abstractmethod
    async def get_images(
        self, contains: str | list[str] | None = None
    ) -> list[str]:  # pragma: no cover
        """Get container images using conatiner engine command.

        :param contains: A substring search filter. Defaults to `None`.
        :type contains: str | list[str] | None, optional
        :return: A list of found container image names.
        :rtype: list[str]
        """
        raise NotImplementedError()

    @abstractmethod
    def create_networks(
        self, logger_name: str, network_names: list[str], to_stdout: bool = False
    ) -> ErrorCode:
        raise NotImplementedError()

    @abstractmethod
    async def get_networks(
        self, contains: str | list[str] | None = None
    ) -> list[str]:  # pragma: no cover
        """Get a list of container network names using container engine command.

        :param contains: A substring search filter. Defaults to `None`.
        :type contains: str | list[str] | None
        :return: A list of found network names.
        :rtype: list[str]
        """
        raise NotImplementedError()

    @abstractmethod
    def rm_network(self, logger_name: str, name: str, to_stdout: bool = False) -> ErrorCode:
        raise NotImplementedError()

    @abstractmethod
    async def rm_images(
        self, logger_name: str, contains: str | list[str], to_stdout: bool = False
    ) -> ErrorCode:  # pragma: no cover
        """Remove container images from the system using container engine command.

        :param logger: A logger handler to write output to.
        :type logger: Logger
        :param contains: A substring search filter.
        :type contains: str | list[str]
        :param to_stdout: Pipe output to stdout as well. Defaults to False.
        :type to_stdout: bool
        :return: An exit code.
        :rtype: int
        """
        raise NotImplementedError()

    # @abstractmethod
    # async def rm_networks(
    #     self, logger_name: str, contains: str | list[str], to_stdout: bool = False
    # ) -> ErrorCode:  # pragma: no cover
    #     """Remove container networks from the system using container engine command.
    #
    #     :param logger: A logger handler to write output to.
    #     :type logger: Logger
    #     :param contains: A substring search filter.
    #     :type contains: str | list[str]
    #     :param to_stdout: Pipe output to stdout as well. Defaults to False.
    #     :type to_stdout: bool
    #     :return: An exit code.
    #     :rtype: int
    #     """
    #     raise NotImplementedError()

    @abstractmethod
    async def compose_up(
        self, logger_name: str, files: list[Path], to_stdout: bool = False
    ) -> ErrorCode:  # pragma: no cover
        """Run compose up for the given file.

        :param logger: A logger handler to write output to.
        :type logger: Logger
        :param file: Path to the compose file.
        :type file: str | Path
        :param to_stdout: Pipe output to stdout as well. Defaults to False.
        :type to_stdout: bool
        :return: An exit code.
        :rtype: int
        """
        raise NotImplementedError()

    @abstractmethod
    async def compose_down(
        self, logger_name: str, files: list[Path], to_stdout: bool = False
    ) -> tuple[ErrorCode, TaskSuccess]:  # pragma: no cover
        """Run compose down for the given compose files.

        Runs ``compose ps -q`` first. When no container IDs are returned, skips ``down`` and
        returns ``(0, False)``. Otherwise runs ``compose down`` and returns
        ``(exit_code, True)`` on success.

        :param logger_name: Logger name for compose engine output
        :type logger_name: str
        :param files: Compose file paths
        :type files: list[Path]
        :param to_stdout: Pipe output to stdout as well. Defaults to False.
        :type to_stdout: bool
        :return: Exit code and whether teardown ran
        :rtype: tuple[ErrorCode, TaskSuccess]
        """
        raise NotImplementedError()

    @abstractmethod
    async def compose_ps(self, files: list[Path]) -> list[str]:  # pragma: no cover
        """List running compose containers via ``compose ps -q``.

        :param files: Compose file paths. An empty list returns ``[]`` without calling the engine.
        :type files: list[Path]
        :return: Container IDs (one per running container), or ``[]`` when none are running
        :rtype: list[str]
        """
        raise NotImplementedError()

    @abstractmethod
    async def compose_ps_json(self, files: list[Path]) -> list[dict[str, Any]]:  # pragma: no cover
        """Get container states in JSON format using compose command.

        :param files: List of compose file paths
        :type files: list[Path]
        :return: A status info for each found container.
        :rtype: list[dict[str, Any]]
        """
        raise NotImplementedError()

    @abstractmethod
    async def compose_build(
        self, logger_name: str, files: list[Path], to_stdout: bool = False
    ) -> ErrorCode:  # pragma: no cover
        """Build container images using `podman-compose` command.

        :param logger: A logger handler to write output to.
        :type logger: Logger
        :param file: Path to the compose file.
        :type file: str | Path
        :param to_stdout: Pipe output to stdout as well. Defaults to False.
        :type to_stdout: bool
        :return: An exit code.
        :rtype: int
        """
        raise NotImplementedError()

    @abstractmethod
    async def compose_logs(
        self,
        logger_name: str,
        files: list[Path],
        *,
        tail: int = 500,
        service: str | None = None,
        to_stdout: bool = True,
    ) -> ErrorCode:  # pragma: no cover
        """Print recent logs from compose services (bounded tail).

        :param logger_name: Logger name for file output
        :param files: Compose file paths
        :param tail: Max lines per service (engine-specific)
        :param service: If set, restrict to this service name
        :param to_stdout: Also echo lines to the default print logger
        """
        raise NotImplementedError()

    @abstractmethod
    async def compose_logs_text(
        self,
        files: list[Path],
        *,
        tail: int = 500,
        service: str | None = None,
    ) -> str:  # pragma: no cover
        """Return recent compose service logs as text (bounded tail).

        Unlike :meth:`compose_logs`, nothing is echoed or written to log
        files — callers (e.g. the admin TUI) render the text themselves.

        :param files: Compose file paths
        :param tail: Max lines per service (engine-specific)
        :param service: If set, restrict to this service name
        :return: Combined stdout/stderr of the logs command; empty string when
            no compose files are given.
        """
        raise NotImplementedError()

    @abstractmethod
    def compose_shell(
        self, files: list[Path], service: str, command: str
    ) -> subprocess.CompletedProcess:  # pragma: no cover
        """Shell into the container using `podman-compose` command.

        :param files: List of compose file paths
        :type files: list[Path]
        :param service: Name of the service within the compose file
        :type service: str
        :param command: A command that will be executed
        :type command: str
        :return: A completed process object
        :rtype: subprocess.CompletedProcess
        """
        raise NotImplementedError()

    @abstractmethod
    async def stats(self, project_name: str) -> list[dict[str, str]]:  # pragma: no cover
        """Get containers' resource usage using `podman stats` command.

        :param project_name: Project name.
        :type: str
        :return: Stats data for the given project.
        :rtype: list[dict[str, str]]
        """
        raise NotImplementedError()

    @abstractmethod
    async def ps(self, project_name: str) -> list[str]:  # pragma: no cover
        """Get containers' states using `podman ps` command.

        :param project_name: Project name.
        :type: str
        :return: Output lines from the `podman` command.
        :rtype: list[str]
        """
        raise NotImplementedError()

    @abstractmethod
    async def ps_json(self, project_name: str) -> list[dict[str, Any]]:  # pragma: no cover
        """Get containers' states in JSON format using `podman ps` command.

        :param project_name: Project name.
        :type: str
        :return: A dict with Podman process data.
        :rtype: list[dict[str, Any]]
        """
        raise NotImplementedError()

    @abstractmethod
    async def ps_csv(self, project_name: str, output_file: pathlib.Path):  # pragma: no cover
        """Generate CSV file for container states.

        :param project_name: Project name.
        :type project_name: str
        :param output_file: The path to the destination file.
        :type output_file: pathlib.Path
        """
        raise NotImplementedError()

    @abstractmethod
    async def compose_states(self, files: list[Path]) -> list[HealthCheckDict]:  # pragma: no cover
        """Returns a simple table that shows the state of each service in the cluster.

        :param files: List of compose file paths
        :type files: list[Path]
        :return: A basic status for each service
        :rtype: list[HealthCheckDict]
        """
        raise NotImplementedError()

    @abstractmethod
    async def project_stats(self, project_name: str) -> list[dict]:  # pragma: no cover
        raise NotImplementedError()

    @abstractmethod
    async def build_image(
        self,
        logger_name: str,
        context_path: pathlib.Path,
        image_name: str,
        containerfile: str = "Containerfile",
        to_stdout: bool = False,
    ) -> ErrorCode:  # pragma: no cover
        """Build a container image from a Containerfile/Dockerfile.

        :param logger_name: Logger name for output
        :type logger_name: str
        :param context_path: Path to build context directory
        :type context_path: pathlib.Path
        :param image_name: Name to tag the built image
        :type image_name: str
        :param containerfile: Name of Containerfile/Dockerfile (default: "Containerfile")
        :type containerfile: str
        :param to_stdout: Pipe output to stdout as well. Defaults to False.
        :type to_stdout: bool
        :return: An exit code
        :rtype: ErrorCode
        """
        raise NotImplementedError()

    @abstractmethod
    async def build_image_text(
        self,
        context_path: Path,
        image_name: str,
        containerfile: str = "Containerfile",
    ) -> tuple[ErrorCode, str]:  # pragma: no cover
        """Build a container image and return ``(exit_code, combined output)``.

        Unlike :meth:`build_image`, nothing is echoed or written to log files —
        callers (e.g. the admin TUI) render the build output themselves.
        """
        raise NotImplementedError()
