"""Render a "what compile would produce" preview of a scenario config.

Pure helper shared by both gateways: it substitutes the draft's values into
the compose template the same way ``ScenarioCompiler.build_param_map`` does
(``{svc}__env_map__{K}``, ``{svc}__port_map__{K}``, ``{svc}__volume_map__{V}``,
``config_params``), and fills the compile-supplied variables (paths, networks,
``project_name``, ``username``, ports) with readable ``<placeholder>`` values —
those are only known at real compile time for a concrete cluster.
"""

from __future__ import annotations

import jinja2

_PLACEHOLDER_EXTRAS: dict[str, str] = {
    "project_name": "<project>",
    "username": "<user>",
    "container_port": "<container_port>",
    "forwarded_port": "<forwarded_port>",
    "login_node_module": "<login_node_module>",
    "paths__projects": "<paths:projects>",
    "paths__users": "<paths:users>",
    "paths__modules": "<paths:modules>",
    "paths__scenarios": "<paths:scenarios>",
    "network_map__shared": "<shared_net>",
    "network_map__private": "<private_net>",
    "network_map__operational": "<operational_net>",
}


def build_preview_param_map(normalized_raw: dict) -> dict[str, object]:
    """Param map from a normalized draft dict + placeholder compile extras."""
    param_map: dict[str, object] = dict(_PLACEHOLDER_EXTRAS)
    param_map.update(normalized_raw.get("config_params", {}))
    for service_name, svc in normalized_raw.get("service_configs", {}).items():
        for key, value in svc.get("env_map", {}).items():
            param_map[f"{service_name}__env_map__{key}"] = value
        for key, value in svc.get("port_map", {}).items():
            param_map[f"{service_name}__port_map__{key}"] = value
        for volume_name, volume in svc.get("volume_map", {}).items():
            # real compile materializes/copies the source; show it verbatim
            param_map[f"{service_name}__volume_map__{volume_name}"] = volume.get(
                "src_path", "<src_path>"
            )
    return param_map


def render_compiled_preview(compose_text: str, normalized_raw: dict) -> str:
    """Best-effort render of the compose template with the draft's values.

    Returns a readable error string (never raises) when the template is
    invalid or references variables the draft does not provide.
    """
    param_map = build_preview_param_map(normalized_raw)
    env = jinja2.Environment(undefined=jinja2.StrictUndefined)
    try:
        rendered = env.from_string(compose_text).render(**param_map)
    except jinja2.UndefinedError as exc:
        return (
            f"# Cannot render preview: {exc.message}\n"
            "# Fill the missing value (service maps, secrets in volume templates, "
            "or config params) and try again.\n"
        )
    except jinja2.TemplateError as exc:
        return f"# Cannot render preview — template error: {exc}\n"
    header = (
        "# Compiled preview — placeholder values (<project>, <user>, ports, paths,\n"
        "# networks) are substituted with real ones when the cluster compiles.\n"
    )
    return header + rendered
