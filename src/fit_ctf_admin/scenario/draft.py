"""Draft scenario-config handling: string-tolerant editing → ScenarioConfig.

While a config is being edited in the TUI, values live in a plain ``dict``
(the same canonical shape the CLI's YAML editor uses) where ports may still be
empty strings. :func:`normalize_draft` turns that draft into a clean raw dict
plus field-addressable error messages; :func:`draft_to_config` builds the
pydantic :class:`ScenarioConfig` from a clean draft.
"""

from __future__ import annotations

import copy
from typing import Any

from fit_ctf.models.infra.config_models import ScenarioConfig
from fit_ctf.models.infra.utils import scenario_config_from_dict

DRAFT_KEYS = ("secrets", "service_configs", "config_params")


def scaffold_draft(
    secret_keys: list[str],
    variables_scaffold: dict,
    config_param_keys: set[str] | None = None,
) -> dict:
    """Build an empty draft from what the scenario templates require."""
    return {
        "secrets": {key: "" for key in secret_keys},
        "service_configs": copy.deepcopy(variables_scaffold),
        "config_params": {key: "" for key in sorted(config_param_keys or set())},
    }


def config_to_draft(config: ScenarioConfig) -> dict:
    """Turn an assigned ScenarioConfig back into an editable draft dict."""
    dump = config.model_dump()
    return {
        "secrets": dict(dump.get("secrets", {})),
        "service_configs": {
            name: {
                "env_map": dict(svc.get("env_map", {})),
                "port_map": {k: str(v) for k, v in svc.get("port_map", {}).items()},
                "volume_map": {
                    vol: {
                        "src_path": vc.get("src_path", ""),
                        "template_params": dict(vc.get("template_params", {})),
                    }
                    for vol, vc in svc.get("volume_map", {}).items()
                },
            }
            for name, svc in dump.get("service_configs", {}).items()
        },
        "config_params": dict(dump.get("config_params", {})),
    }


def normalize_draft(raw: dict) -> tuple[dict, list[str]]:
    """Validate draft structure and coerce port strings to integers.

    Returns ``(normalized_raw, errors)``. The normalized dict is only usable
    when ``errors`` is empty.
    """
    errors: list[str] = []
    normalized: dict[str, Any] = {
        "secrets": {},
        "service_configs": {},
        "config_params": {},
    }

    secrets = raw.get("secrets") or {}
    if not isinstance(secrets, dict):
        errors.append("'secrets' must be a mapping")
        secrets = {}
    for key, value in secrets.items():
        key = str(key).strip()
        if not key:
            errors.append("secret keys must not be empty")
            continue
        if "__" in key:
            errors.append(f"secret key {key!r} must not contain '__'")
            continue
        normalized["secrets"][key] = "" if value is None else str(value)

    services = raw.get("service_configs") or {}
    if not isinstance(services, dict):
        errors.append("'service_configs' must be a mapping")
        services = {}
    for service_name, svc in services.items():
        if not isinstance(svc, dict):
            errors.append(f"service {service_name!r} must be a mapping")
            continue
        out_svc: dict[str, Any] = {"env_map": {}, "port_map": {}, "volume_map": {}}
        for key, value in (svc.get("env_map") or {}).items():
            out_svc["env_map"][str(key)] = "" if value is None else str(value)
        for key, value in (svc.get("port_map") or {}).items():
            text = str(value).strip() if value is not None else ""
            if not text:
                errors.append(f"{service_name}.port_map.{key}: enter a port number")
                continue
            try:
                port = int(text)
            except ValueError:
                errors.append(f"{service_name}.port_map.{key}: {text!r} is not an integer")
                continue
            if not 1 <= port <= 65_535:
                errors.append(f"{service_name}.port_map.{key}: {port} is out of range 1–65535")
                continue
            out_svc["port_map"][str(key)] = port
        for volume_name, volume in (svc.get("volume_map") or {}).items():
            if not isinstance(volume, dict):
                errors.append(f"{service_name}.volume_map.{volume_name} must be a mapping")
                continue
            src_path = str(volume.get("src_path") or "").strip()
            if not src_path:
                errors.append(f"{service_name}.volume_map.{volume_name}.src_path: enter a path")
            out_svc["volume_map"][str(volume_name)] = {
                "src_path": src_path,
                "template_params": {
                    str(k): "" if v is None else v
                    for k, v in (volume.get("template_params") or {}).items()
                },
            }
        normalized["service_configs"][str(service_name)] = out_svc

    params = raw.get("config_params") or {}
    if not isinstance(params, dict):
        errors.append("'config_params' must be a mapping")
        params = {}
    for key, value in params.items():
        normalized["config_params"][str(key)] = "" if value is None else value

    unknown = set(raw.keys()) - set(DRAFT_KEYS)
    if unknown:
        errors.append(f"unknown top-level keys: {sorted(unknown)!r}")
    return normalized, errors


def draft_to_config(scenario_name: str, normalized_raw: dict) -> ScenarioConfig:
    """Build a :class:`ScenarioConfig` from a normalized draft dict."""
    return scenario_config_from_dict(scenario_name, normalized_raw)
