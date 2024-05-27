from __future__ import annotations

import subprocess
import sys


def podman_get_images(contains: str | list[str] | None = None) -> list[str]:
    cmd = ["podman", "images", "--format", '"{{ .Repository }}"']
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


def podman_get_networks(contains: str | list[str] | None = None) -> list[str]:
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
    images = podman_get_images(contains)
    if not images:
        return
    cmd = ["podman", "rmi"] + images
    return subprocess.run(cmd, stdout=sys.stdout, stderr=sys.stderr)


def podman_rm_networks(contains: str) -> subprocess.CompletedProcess | None:
    images = podman_get_networks(contains)
    if not images:
        return
    cmd = ["podman", "network", "rm"] + images
    return subprocess.run(cmd, stdout=sys.stdout, stderr=sys.stderr)


def podman_compose_up(file: str) -> subprocess.CompletedProcess:
    # TODO: eliminate whitespaces
    cmd = f"podman-compose -f {file} up -d"
    proc = subprocess.run(
        cmd.split(),
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    return proc


def podman_compose_down(file: str) -> subprocess.CompletedProcess:
    # TODO: eliminate whitespaces
    cmd = f"podman-compose -f {file} down"
    proc = subprocess.run(
        cmd.split(),
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    return proc


def podman_compose_ps(file: str) -> list[str]:
    cmd = ["podman-compose", "-f", file, "ps", "--format", '"{{ .Names }}"']
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return [data.lstrip('"').rstrip('"') for data in proc.stdout.rsplit()]


def podman_stats(project_name: str) -> subprocess.CompletedProcess:
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
    cmd = [
        "podman",
        "ps",
        "-a",
        "--format",
        "table {{.Names}} {{.Networks}} {{.Ports}} {{.State}} {{.CreatedHuman}}",
        f"--filter=name=^{project_name}"
    ]
    return subprocess.run(cmd, stdout=sys.stdout, stderr=sys.stderr)

