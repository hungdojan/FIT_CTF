"""Export a visual design to FIT-CTF Compose/Jinja preview text."""

from __future__ import annotations

from fit_ctf_admin.scenario.design_model import (
    BUILTIN_NETWORKS,
    ScenarioDesign,
    ServiceBlock,
    is_builtin_network,
    network_jinja_key,
)


def _network_ref(name: str) -> str:
    if is_builtin_network(name):
        key = network_jinja_key(name)
        return f"{{{{ {key} }}}}"
    return name


def _network_lines(block: ServiceBlock) -> list[str]:
    lines: list[str] = []
    for network in block.networks:
        lines.append(f"      {_network_ref(network)}:")
    return lines or ["      {{ network_map__shared }}:"]


def _port_lines(block: ServiceBlock) -> list[str]:
    if not block.ports:
        return []
    lines = ["    ports:"]
    for name, host_port in block.ports.items():
        lines.append(f'      - "{{{{ {block.service_key}__port_map__{name} }}}}:{host_port}"')
    return lines


def _env_lines(block: ServiceBlock) -> list[str]:
    if not block.env_keys:
        return []
    lines = ["    environment:"]
    for key in block.env_keys:
        lines.append(f'      - "{key}={{{{ {block.service_key}__env_map__{key} }}}}"')
    return lines


def _container_name_lines(block: ServiceBlock) -> list[str]:
    if block.container_name_mode != "concrete" or not block.container_name:
        return []
    return [f"    container_name: {block.container_name}"]


def _volume_lines(block: ServiceBlock) -> list[str]:
    if not block.volumes:
        return []
    lines = ["    volumes:"]
    for slot in block.volumes:
        suffix = ":ro" if slot.read_only else ""
        lines.append(
            f'      - "{{{{ {block.service_key}__volume_map__{slot.name} }}}}:'
            f'{slot.container_path}{suffix}"'
        )
    return lines


def export_service_block(block: ServiceBlock) -> str:
    if block.image_source == "image":
        # external image: pulled as-is, nothing to build from modules/
        lines = [
            f"  {block.service_key}:",
            f"    image: {block.image_ref}",
        ]
    else:
        lines = [
            f"  {block.service_key}:",
            "    build:",
            f"      context: {{{{ paths__modules }}}}/{block.module_name}",
            "      dockerfile: Containerfile",
            f"    image: fit-ctf/{block.module_name}:latest",
        ]
    lines.extend(_container_name_lines(block))
    lines.extend(
        [
            "    restart: unless-stopped",
            "    networks:",
            *_network_lines(block),
        ]
    )
    lines.extend(_port_lines(block))
    lines.extend(_env_lines(block))
    lines.extend(_volume_lines(block))
    return "\n".join(lines)


def export_compose_preview(design: ScenarioDesign) -> str:
    if not design.blocks:
        header = [
            "# Add service blocks on the canvas to generate a compose preview.",
            f"# Scenario name: {design.name}",
        ]
        if design.secrets:
            header.extend(
                [
                    "",
                    "# Secrets (configured at compile time):",
                    *[f"# - {key}" for key in sorted(design.secrets)],
                ]
            )
        return "\n".join(header)

    used: list[str] = []
    for block in design.blocks:
        for network in block.networks:
            if network not in used:
                used.append(network)
    ordered = [n for n in BUILTIN_NETWORKS if n in used]
    ordered.extend(n for n in used if not is_builtin_network(n))

    # project clusters render with only {{ project_name }}; {{ username }} is
    # available on user clusters alone — a wrong name line breaks compile
    if design.target_kind == "project":
        name_line = f'name: "{{{{ project_name }}}}_{design.name}"'
    else:
        name_line = f'name: "{{{{ project_name }}}}_{{{{ username }}}}_{design.name}"'
    lines = [
        "---",
        name_line,
        "",
        "services:",
    ]
    lines.extend(export_service_block(block) for block in design.blocks)

    if design.secrets:
        lines.extend(["", "# Secrets (scenario config — volume template injection):", "#"])
        for key in sorted(design.secrets):
            lines.append(f"# secret_map__{key} = <configured at compile time>")

    lines.extend(["", "networks:"])
    for network in ordered:
        if is_builtin_network(network):
            key = network_jinja_key(network)
            lines.append(f"  {{{{ {key} }}}}:")
        else:
            lines.append(f"  {network}:")
        lines.append("    external: true")

    return "\n".join(lines)
