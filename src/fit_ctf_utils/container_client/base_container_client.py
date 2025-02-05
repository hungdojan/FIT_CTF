from __future__ import annotations

import subprocess
from abc import ABC, abstractmethod
from logging import Logger
from pathlib import Path
from typing import Any


class BaseContainerClient(ABC):

    @classmethod
    @abstractmethod
    def get_images(
        cls, contains: str | list[str] | None = None
    ) -> list[str]:  # pragma: no cover
        """Get container images using `podman` command.

        :param contains: A substring search filter. Defaults to `None`.
        :type contains: str | list[str] | None, optional
        :return: A list of found container image names.
        :rtype: list[str]
        """
        pass

    @classmethod
    @abstractmethod
    def get_networks(
        cls, contains: str | list[str] | None = None
    ) -> list[str]:  # pragma: no cover
        """Get a list of container network names using `podman` command.

        :param contains: A substring search filter. Defaults to `None`.
        :type contains: str | list[str] | None
        :return: A list of found network names.
        :rtype: list[str]
        """
        pass

    @classmethod
    @abstractmethod
    def rm_images(
        cls, logger: Logger, contains: str, to_stdout: bool = False
    ) -> int:  # pragma: no cover
        """Remove container images from the system using `podman` command.

        :param logger: A logger handler to write output to.
        :type logger: Logger
        :param contains: A substring search filter.
        :type contains: str
        :param to_stdout: Pipe output to stdout as well. Defaults to False.
        :type to_stdout: bool
        :return: An exit code.
        :rtype: int
        """
        pass

    @classmethod
    @abstractmethod
    def rm_multiple_images(
        cls, logger: Logger, image_names: list[str], to_stdout: bool = False
    ) -> int:  # pragma: no cover
        """Remove numerous container images from the system using `podman` command.

        :param logger: A logger handler to write output to.
        :type logger: Logger
        :param image_names: A list of images to remove.
        :type image_names: list[str]
        :param to_stdout: Pipe output to stdout as well. Defaults to False.
        :type to_stdout: bool
        :return: An exit code.
        :rtype: int
        """
        pass

    @classmethod
    @abstractmethod
    def rm_networks(
        cls, logger: Logger, contains: str, to_stdout: bool = False
    ) -> int:  # pragma: no cover
        """Remove container networks from the system using `podman` command.

        :param logger: A logger handler to write output to.
        :type logger: Logger
        :param contains: A substring search filter.
        :type contains: str
        :param to_stdout: Pipe output to stdout as well. Defaults to False.
        :type to_stdout: bool
        :return: An exit code.
        :rtype: int
        """
        pass

    @classmethod
    @abstractmethod
    def rm_multiple_networks(
        cls, logger: Logger, network_names: list[str], to_stdout: bool = False
    ) -> int:  # pragma: no cover
        """Remove numerous container networks from the system using `podman` command.

        :param logger: A logger handler to write output to.
        :type logger: Logger
        :param network_names: A list of network names to remove.
        :type network_names: list[str]
        :param to_stdout: Pipe output to stdout as well. Defaults to False.
        :type to_stdout: bool
        :return: An exit code.
        :rtype: int
        """
        pass

    @classmethod
    @abstractmethod
    def compose_up(
        cls, logger: Logger, file: str | Path, to_stdout: bool = False
    ) -> int:  # pragma: no cover
        """Run `podman-compose up` for the given file.

        :param logger: A logger handler to write output to.
        :type logger: Logger
        :param file: Path to the compose file.
        :type file: str | Path
        :param to_stdout: Pipe output to stdout as well. Defaults to False.
        :type to_stdout: bool
        :return: An exit code.
        :rtype: int
        """
        pass

    @classmethod
    @abstractmethod
    def compose_down(
        cls, logger: Logger, file: str | Path, to_stdout: bool = False
    ) -> int:  # pragma: no cover
        """Run `podman-compose down` for the given file.

        :param logger: A logger handler to write output to.
        :type logger: Logger
        :param file: Path to the compose file.
        :type file: str | Path
        :param to_stdout: Pipe output to stdout as well. Defaults to False.
        :type to_stdout: bool
        :return: An exit code.
        :rtype: int
        """
        pass

    @classmethod
    @abstractmethod
    def compose_ps(cls, file: str | Path) -> list[str]:  # pragma: no cover
        """Get container states using `podman-compose` command.

        :param file: Path to the compose file.
        :type file: str | Path
        :return: A status info for each found container.
        :rtype: list[str]
        """
        pass

    @classmethod
    @abstractmethod
    def compose_ps_json(
        cls, file: str | Path
    ) -> list[dict[str, Any]]:  # pragma: no cover
        """Get container states in JSON format using `podman-compose` command.

        :param file: Path to the compose file.
        :type file: str | Path
        :return: A status info for each found container.
        :rtype: list[dict[str, Any]]
        """
        pass

    @classmethod
    @abstractmethod
    def compose_build(
        cls, logger: Logger, file: str | Path, to_stdout: bool = False
    ) -> int:  # pragma: no cover
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
        pass

    @classmethod
    @abstractmethod
    def compose_shell(
        cls, file: str | Path, service: str, command: str
    ) -> subprocess.CompletedProcess:  # pragma: no cover
        """Shell into the container using `podman-compose` command.

        :param file: A path to the compose file.
        :type file: str | Path
        :param service: Name of the service within the compose file.
        :type service: str
        :param command: A command that will be executed.
        :type command: str
        :return: A completed process object.
        :rtype: subprocess.CompletedProcess
        """
        pass

    @classmethod
    @abstractmethod
    def stats(cls, project_name: str) -> list[dict[str, str]]:  # pragma: no cover
        """Get containers' resource usage using `podman stats` command.

        :param project_name: Project name.
        :type: str
        :return: Stats data for the given project.
        :rtype: list[dict[str, str]]
        """
        pass

    @classmethod
    @abstractmethod
    def ps(cls, project_name: str) -> list[str]:  # pragma: no cover
        """Get containers' states using `podman ps` command.

        :param project_name: Project name.
        :type: str
        :return: Output lines from the `podman` command.
        :rtype: list[str]
        """
        pass

    @classmethod
    @abstractmethod
    def ps_json(cls, project_name: str) -> list[dict[str, Any]]:  # pragma: no cover
        """Get containers' states in JSON format using `podman ps` command.

        :param project_name: Project name.
        :type: str
        :return: A dict with Podman process data.
        :rtype: list[dict[str, Any]]
        """
        pass
