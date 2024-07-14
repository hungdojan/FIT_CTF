from __future__ import annotations

import subprocess
from abc import ABC, abstractmethod


class BaseContainerClient(ABC):

    @classmethod
    @abstractmethod
    def get_images(cls, contains: str | list[str] | None = None) -> list[str]:
        """Get container images using `podman` command.

        :param contains: A substring search filter. Defaults to `None`.
        :type contains: str | list[str] | None, optional
        :return: A list of found container image names.
        :rtype: list[str]
        """
        pass

    @classmethod
    @abstractmethod
    def get_networks(cls, contains: str | list[str] | None = None) -> list[str]:
        """Get a list of container network names using `podman` command.

        :param contains: A substring search filter. Defaults to `None`.
        :type contains: str | list[str] | None
        :return: A list of found network names.
        :rtype: list[str]
        """
        pass

    @classmethod
    @abstractmethod
    def rm_images(cls, contains: str) -> subprocess.CompletedProcess | None:
        """Remove container images from the system using `podman` command.

        :param contains: A substring search filter.
        :type contains: str
        :return: A completed process object when images are successfully removed. None if no
        image with the given substring was found.
        :rtype: subprocess.CompletedProcess | None
        """
        pass

    @classmethod
    @abstractmethod
    def rm_networks(cls, contains: str) -> subprocess.CompletedProcess | None:
        """Remove container networks from the system using `podman` command.

        :param contains: A substring search filter.
        :type contains: str
        :return: A completed process object when networks are successfully removed. None if no
        network with the given substring was found.
        :rtype: subprocess.CompletedProcess | None
        """
        pass

    @classmethod
    @abstractmethod
    def compose_up(cls, file: str) -> subprocess.CompletedProcess:
        """Run `podman-compose up` for the given file.

        :param file: Path to the compose file.
        :type file: str
        :return: A completed process object.
        :rtype: subprocess.CompletedProcess
        """
        pass

    @classmethod
    @abstractmethod
    def compose_down(cls, file: str) -> subprocess.CompletedProcess:
        """Run `podman-compose down` for the given file.

        :param file: Path to the compose file.
        :type file: str
        :return: A completed process object.
        :rtype: subprocess.CompletedProcess
        """
        pass

    @classmethod
    @abstractmethod
    def compose_ps(cls, file: str) -> list[str]:
        """Get container states using `podman-compose` command.

        :param file: Path to the compose file.
        :type file: str
        :return: A status info for each found container.
        :rtype: list[str]
        """
        pass

    @classmethod
    @abstractmethod
    def stats(cls, project_name: str) -> subprocess.CompletedProcess:
        """Get containers' resource usage using `podman stats` command.

        :param project_name: Project name.
        :type: str
        :return: A completed process object.
        :rtype: subprocess.CompletedProcess
        """
        pass

    @classmethod
    @abstractmethod
    def ps(cls, project_name: str) -> subprocess.CompletedProcess:
        """Get containers' states using `podman ps` command.

        :param project_name: Project name.
        :type: str
        :return: A completed process object.
        :rtype: subprocess.CompletedProcess
        """
        pass

    @classmethod
    @abstractmethod
    def shell(
        cls, file: str, service: str, command: str
    ) -> subprocess.CompletedProcess:
        """Shell into the container using `podman-compose` command.

        :param file: A path to the compose file.
        :type file: str
        :param service: Name of the service within the compose file.
        :type service: str
        :param command: A command that will be executed.
        :type command: str
        :return: A completed process object.
        :rtype: subprocess.CompletedProcess
        """
        pass
