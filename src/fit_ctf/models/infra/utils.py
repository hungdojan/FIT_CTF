"""Utility functions for scenario and configuration management.

This module consolidates utility functions from:
- secret_slots.py: Secret ID manipulation
- scenario_config_validation.py: Validation logic
- config_models.py: Config construction helpers
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from fit_ctf.models.utils.exceptions import (
    CTFModelException,
    InvalidDynamicSecretKeyException,
)

if TYPE_CHECKING:
    import fit_ctf.models.infra.project_cluster as project_cluster
    import fit_ctf.models.infra.user_cluster as user_cluster
    from fit_ctf.models.infra.config_models import (
        ScenarioConfig,
        ServiceConfig,
        VolumeConfig,
    )
    from fit_ctf.models.infra.scenario_manager import ScenarioManager


def lint_compiled_compose(compose: dict) -> list[str]:
    """Warnings for compiled-compose constructs the engines reject at runtime.

    Docker compose validates strictly and fails commands like ``ps`` with
    cryptic schema errors (e.g. ``environment.[0] unexpected type
    map[string]interface {}``) long after compilation. This lint runs right
    after compile so the author is pointed at the offending template line.
    Currently checked: list-form ``environment`` entries must be strings —
    an unquoted ``- KEY: value`` line parses as a YAML mapping.
    """
    warnings: list[str] = []
    services = compose.get("services")
    if not isinstance(services, dict):
        return warnings
    for service_name, service in services.items():
        if not isinstance(service, dict):
            continue
        environment = service.get("environment")
        if not isinstance(environment, list):
            continue  # map form (or absent) is valid compose
        for index, entry in enumerate(environment):
            if not isinstance(entry, str):
                warnings.append(
                    f"service '{service_name}': environment entry {index} is "
                    f"{type(entry).__name__ if entry is not None else 'empty'}, not a string — "
                    'write it as a quoted "KEY=value" line in scenario_compose.yaml.j2 '
                    "(docker compose rejects mapping entries)"
                )
    return warnings


def warnings_after_secrets_trial(
    scenario_mgr: "ScenarioManager",
    scenario_name: str,
    scenario_config: "ScenarioConfig",
    secrets_delta: dict[str, str | None],
) -> list[str]:
    """Deep-copy ``scenario_config``, apply ``secrets_delta``, validate vs templates.

    ``None`` in ``secrets_delta`` removes that secret key. May raise
    :class:`CTFModelException` when the post-mutation config is invalid.
    Returns template validation warning strings. Shared by the CLI secret
    commands and the admin TUI.
    """
    trial = scenario_config.model_copy(deep=True)
    for key, value in secrets_delta.items():
        if value is None:
            trial.secrets.pop(key, None)
        else:
            trial.secrets[key] = value
    return scenario_mgr.validate_scenario_config_against_templates(scenario_name, trial)


# Secret ID Utilities

ClusterKind = Literal["user", "project"]

COMPOSITE_SEP = "\x1f"


def composite_secret_id(cluster_kind: ClusterKind, scenario_name: str, local_name: str) -> str:
    return COMPOSITE_SEP.join((cluster_kind, scenario_name, local_name))


def parse_composite_secret_id(composite_id: str) -> tuple[ClusterKind, str, str]:
    parts = composite_id.split(COMPOSITE_SEP, 2)
    if len(parts) != 3:
        raise ValueError(f"Invalid composite secret id: {composite_id!r}")
    kind, scenario, local = parts
    if kind not in ("user", "project"):
        raise ValueError(f"Invalid cluster kind in composite id: {kind!r}")
    return kind, scenario, local  # type: ignore[return-value]


def format_composite_for_display(composite_id: str) -> str:
    return composite_id.replace(COMPOSITE_SEP, "/")


def flatten_scenario_secrets(
    cluster_kind: ClusterKind,
    scenario_configs: dict[str, ScenarioConfig],
) -> dict[str, str]:
    """Map composite_id -> expected secret string (opaque; may be human-chosen or random)."""
    out: dict[str, str] = {}
    for scenario_name, cfg in scenario_configs.items():
        for local_name, val in cfg.secrets.items():
            cid = composite_secret_id(cluster_kind, scenario_name, local_name)
            out[cid] = val
    return out


def merged_submission_secret_map(
    user_cluster: "user_cluster.UserCluster | None",
    project_cluster: "project_cluster.ProjectCluster | None",
) -> dict[str, str]:
    m: dict[str, str] = {}
    if project_cluster is not None:
        m.update(flatten_scenario_secrets("project", project_cluster.scenario_configs))
    if user_cluster is not None:
        m.update(flatten_scenario_secrets("user", user_cluster.scenario_configs))
    return m


def count_submittable_secret_slots(
    user_cluster: "user_cluster.UserCluster | None",
    project_cluster: "project_cluster.ProjectCluster | None",
) -> int:
    return len(merged_submission_secret_map(user_cluster, project_cluster))


# Validation Utilities


def validate_secrets_vs_templates(
    required_secret_names: frozenset[str],
    configured_secrets: dict[str, str],
) -> tuple[list[str], list[str]]:
    """Return ``(errors, warnings)`` for secret keys vs ``secret_map__*`` template usage."""
    errors: list[str] = []
    warnings: list[str] = []
    configured = set(configured_secrets.keys())
    for name in sorted(required_secret_names - configured):
        errors.append(f"missing secrets['{name}'] (templates use secret_map__{name})")
    for name in sorted(configured - required_secret_names):
        warnings.append(f"unused secrets['{name}'] (no secret_map__{name} in scenario templates)")
    return errors, warnings


def _warn_unused_map_keys(
    warnings: list[str],
    *,
    svc: str,
    label: str,
    user_keys: Any,
    scaffold_keys: Any,
) -> None:
    """Emit warnings for keys present in user config but not in the template scaffold."""
    for k in set(user_keys) - set(scaffold_keys):
        warnings.append(f"service '{svc}' has unused {label} key '{k}'")


def _validate_env_map(
    errors: list[str],
    warnings: list[str],
    svc: str,
    scm_env: dict[str, Any],
    cfg: ServiceConfig,
) -> None:
    for ek in scm_env:
        if ek not in cfg.env_map:
            errors.append(f"service '{svc}' missing env_map key '{ek}' required by templates")
        elif not str(cfg.env_map.get(ek, "")).strip():
            errors.append(f"service '{svc}' env_map['{ek}'] is empty but required by templates")
    _warn_unused_map_keys(
        warnings, svc=svc, label="env_map", user_keys=cfg.env_map, scaffold_keys=scm_env
    )


def _validate_port_map(
    errors: list[str],
    warnings: list[str],
    svc: str,
    scm_ports: dict[str, Any],
    cfg: ServiceConfig,
) -> None:
    for pk in scm_ports:
        if pk not in cfg.port_map:
            errors.append(f"service '{svc}' missing port_map key '{pk}' required by templates")
            continue
        try:
            pv = int(cfg.port_map[pk])
        except (TypeError, ValueError):
            errors.append(f"service '{svc}' port_map['{pk}'] must be an integer port")
        else:
            if not (1 <= pv <= 65_535):
                errors.append(f"service '{svc}' port_map['{pk}'] must be in range 1-65535")
    _warn_unused_map_keys(
        warnings,
        svc=svc,
        label="port_map",
        user_keys=cfg.port_map,
        scaffold_keys=scm_ports,
    )


def _validate_volume_map(
    errors: list[str],
    warnings: list[str],
    svc: str,
    scm_vols: dict[str, Any],
    vol_map: dict[str, VolumeConfig],
) -> None:
    for vk, vv in scm_vols.items():
        # ``fetch_variables`` only builds dict-shaped volume entries.
        if not isinstance(vv, dict):
            continue
        if vk not in vol_map:
            errors.append(f"service '{svc}' missing volume_map volume '{vk}' required by templates")
            continue
        uv = vol_map[vk]
        if "src_path" in vv and not str(uv.src_path).strip():
            errors.append(
                f"service '{svc}' volume '{vk}' src_path is empty but required by templates"
            )
        scm_tpl = vv.get("template_params", {})
        for tk in scm_tpl:
            if tk not in uv.template_params:
                errors.append(
                    f"service '{svc}' volume '{vk}' missing template_params key '{tk}' "
                    "required by templates"
                )
            elif not str(uv.template_params.get(tk, "")).strip():
                errors.append(
                    f"service '{svc}' volume '{vk}' template_params['{tk}'] is empty "
                    "but required by templates"
                )
        for tk in uv.template_params:
            if tk not in scm_tpl:
                warnings.append(
                    f"service '{svc}' volume '{vk}' has unused template_params key '{tk}'"
                )
    for vk in vol_map:
        if vk not in scm_vols:
            warnings.append(f"service '{svc}' has unused volume_map volume '{vk}'")


def validate_service_configs_vs_scaffold(
    scaffold: dict[str, Any],
    service_configs: dict[str, ServiceConfig],
) -> tuple[list[str], list[str]]:
    """Compare ``fetch_variables`` scaffold to configured services."""
    errors: list[str] = []
    warnings: list[str] = []

    for svc, sc_data in scaffold.items():
        if svc not in service_configs:
            errors.append(f"missing service '{svc}' required by scenario templates")
            continue
        cfg = service_configs[svc]
        _validate_env_map(errors, warnings, svc, sc_data.get("env_map", {}), cfg)
        _validate_port_map(errors, warnings, svc, sc_data.get("port_map", {}), cfg)
        _validate_volume_map(errors, warnings, svc, sc_data.get("volume_map", {}), cfg.volume_map)

    for svc in service_configs:
        if svc not in scaffold:
            warnings.append(f"unused service '{svc}' not referenced by scenario templates")

    return errors, warnings


# Config Construction Utilities

CANONICAL_SCENARIO_YAML_KEYS = frozenset({"secrets", "service_configs"})


def validate_canonical_scenario_yaml_dict(raw: dict) -> dict:
    """Require exactly ``secrets`` and ``service_configs`` (add-scenario / vars-template shape)."""
    if set(raw.keys()) != CANONICAL_SCENARIO_YAML_KEYS:
        raise CTFModelException(
            "Scenario YAML must have exactly top-level keys "
            f"{sorted(CANONICAL_SCENARIO_YAML_KEYS)!r}, got {sorted(raw.keys())!r}"
        )
    sec = raw["secrets"]
    svc = raw["service_configs"]
    if not isinstance(sec, dict):
        raise CTFModelException("'secrets' must be a mapping")
    if not isinstance(svc, dict):
        raise CTFModelException("'service_configs' must be a mapping")
    for name in sec:
        if "__" in str(name):
            raise InvalidDynamicSecretKeyException(
                f"secrets key {name!r} must not contain '__' (Jinja uses secret_map__<name>)."
            )
    return raw


def service_config_from_dict(raw: dict) -> ServiceConfig:
    """Build ServiceConfig from a YAML/dump dict (setup.yaml / database_dump)."""
    from fit_ctf.models.infra.config_models import ServiceConfig, VolumeConfig

    volume_map: dict[str, VolumeConfig] = {}
    for k, v in raw.get("volume_map", {}).items():
        if isinstance(v, VolumeConfig):
            volume_map[k] = v
        else:
            volume_map[k] = VolumeConfig(**v)
    return ServiceConfig(
        env_map=dict(raw.get("env_map", {})),
        port_map=dict(raw.get("port_map", {})),
        volume_map=volume_map,
    )


def scenario_config_from_dict(scenario_name: str, raw: dict) -> ScenarioConfig:
    """Build ScenarioConfig from a YAML/dump dict (per setup.yaml scenario_configs)."""
    from fit_ctf.models.infra.config_models import ScenarioConfig

    builder = ScenarioConfig.Builder(scenario_name)
    for name, value in raw.get("secrets", {}).items():
        if "__" in str(name):
            raise InvalidDynamicSecretKeyException(
                f"secrets key {name!r} must not contain '__' (Jinja uses secret_map__<name>)."
            )
        builder.add_secret(name, value if isinstance(value, str) else str(value))
    for service_name, svc_raw in raw.get("service_configs", {}).items():
        if not isinstance(svc_raw, dict):
            continue
        builder.add_service(service_name, service_config_from_dict(svc_raw))
    for name, value in raw.get("config_params", {}).items():
        builder.add_config_param(name, value)
    return builder.build()
