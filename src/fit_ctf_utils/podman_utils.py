from __future__ import annotations

import subprocess
import sys

import fit_ctf_db_models.project as _project


def podman_get_images(contains: str | list[str] | None = None) -> list[str]:
    """Get container images using `podman` command.

    :param contains: A substring search filter. Defaults to `None`.
    :type contains: str | list[str] | None, optional
    :return: A list of found container image names.
    :rtype: list[str]
    """
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


def podman_get_networks(contains: str | list[str] | None = None) -> list[str]:
    """Get a list of container network names using `podman` command.

    :param conatins: A substring search filter. Defaults to `None`.
    :type contains: str | list[str] | None
    :return: A list of found network names.
    :rtype: list[str]
    """
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


def podman_rm_images(contains: str) -> subprocess.CompletedProcess | None:
    """Remove container images from the system using `podman` command.

    :param contains: A substring search filter.
    :type contains: str
    :return: A completed process object when images are successfully removed. None if no
    image with the given substring was found.
    :rtype: subprocess.CompletedProcess | None
    """
    images = podman_get_images(contains)
    if not images:
        return
    cmd = ["podman", "rmi"] + images
    return subprocess.run(cmd, stdout=sys.stdout, stderr=sys.stderr)


def podman_rm_networks(contains: str) -> subprocess.CompletedProcess | None:
    """Remove container networks from the system using `podman` command.

    :param contains: A substring search filter.
    :type contains: str
    :return: A completed process object when networks are successfully removed. None if no
    network with the given substring was found.
    :rtype: subprocess.CompletedProcess | None
    """
    network_names = podman_get_networks(contains)
    if not network_names:
        return
    cmd = ["podman", "network", "rm"] + network_names
    return subprocess.run(cmd, stdout=sys.stdout, stderr=sys.stderr)


def podman_compose_up(file: str) -> subprocess.CompletedProcess:
    """Run `podman-compose up` for the given file.

    :param file: Path to the compose file.
    :type file: str
    :return: A completed process object.
    :rtype: subprocess.CompletedProcess
    """
    # TODO: eliminate whitespaces
    cmd = f"podman-compose -f {file} up -d"
    # TODO redirect outputs
    proc = subprocess.run(
        cmd.split(),
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    return proc


def podman_compose_down(file: str) -> subprocess.CompletedProcess:
    """Run `podman-compose down` for the given file.

    :param file: Path to the compose file.
    :type file: str
    :return: A completed process object.
    :rtype: subprocess.CompletedProcess
    """
    # TODO: eliminate whitespaces
    cmd = f"podman-compose -f {file} down"
    # TODO: redirect outputs
    proc = subprocess.run(
        cmd.split(),
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    return proc


def podman_compose_ps(file: str) -> list[str]:
    """Get container states using `podman-compose` command.

    :param file: Path to the compose file.
    :type file: str
    :return: A status info for each found container.
    :rtype: list[str]
    """
    cmd = ["podman-compose", "-f", file, "ps", "--format", '"{{ .Names }}"']
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return [data.lstrip('"').rstrip('"') for data in proc.stdout.rsplit()]


def podman_stats(project_name: str) -> subprocess.CompletedProcess:
    """Get containers' resource usage using `podman stats` command.

    :param project_name: Project name.
    :type: str
    :return: A completed process object.
    :rtype: subprocess.CompletedProcess
    """
    cmd = "podman ps -a --format={{.Names}} " f"--filter=name=^{project_name}"
    proc = subprocess.run(cmd.split(), capture_output=True, text=True)

    container_names = [data.rstrip('"').lstrip('"') for data in proc.stdout.rsplit()]
    cmd = [
        "podman",
        "stats",
        "--no-stream",
        "--format",
        "table {{.Name}} {{.CPUPerc}} {{.MemUsage}} {{.UpTime}}",
    ] + container_names
    return subprocess.run(cmd, stdout=sys.stdout, stderr=sys.stderr)


def podman_ps(project_name: str) -> subprocess.CompletedProcess:
    """Get containers' states using `podman ps` command.

    :param project_name: Project name.
    :type: str
    :return: A completed process object.
    :rtype: subprocess.CompletedProcess
    """
    cmd = [
        "podman",
        "ps",
        "-a",
        "--format",
        "table {{.Names}} {{.Networks}} {{.Ports}} {{.State}} {{.CreatedHuman}}",
        f"--filter=name=^{project_name}",
    ]
    return subprocess.run(cmd, stdout=sys.stdout, stderr=sys.stderr)


def podman_shell(file: str, service: str, command: str) -> subprocess.CompletedProcess:
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
    cmd = f"podman-compose -f {file} exec {service} {command}"
    return subprocess.run(cmd.split(), stdout=sys.stdout, stderr=sys.stderr)
