"""Write-back of TUI designs into real scenario directories.

Alongside the generated ``scenario_compose.yaml.j2`` a sidecar
``admin_design.json`` is stored inside the scenario directory. It carries the
full design plus a SHA-256 of the compose text, so:

* re-opening a TUI-authored scenario restores the design with exact fidelity,
* a hash mismatch (or a missing sidecar) marks the scenario as hand-edited /
  foreign, and the UI asks before overwriting it.

The sidecar never leaks into compiled cluster directories —
``ScenarioCompiler.copy_scenario_template_trees`` only copies ``volumes/`` and
``modules/``.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from fit_ctf.models.utils.exceptions import ScenarioNotExistException
from fit_ctf_admin.exceptions import AdminError
from fit_ctf_admin.scenario.compose_export import export_compose_preview
from fit_ctf_admin.scenario.design_model import ScenarioDesign

if TYPE_CHECKING:
    from fit_ctf.models.infra.scenario_manager import ScenarioManager

SIDECAR_NAME = "admin_design.json"
SIDECAR_VERSION = 1

# new: no directory yet; ours: sidecar matches compose; foreign: hand-written
# or edited outside the designer (no sidecar / stale hash)
CollisionState = Literal["new", "ours", "foreign"]


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class DesignerLoadResult:
    design: ScenarioDesign | None
    compose_text: str
    fidelity: Literal["sidecar", "imported", "raw"]


class ScenarioWriter:
    """Save/load scenario designs through :class:`ScenarioManager`."""

    def __init__(self, scenario_mgr: "ScenarioManager") -> None:
        self._mgr = scenario_mgr

    # -- state ---------------------------------------------------------------

    def collision_state(self, name: str) -> CollisionState:
        try:
            compose_text = self._mgr.read_compose_template(name)
        except ScenarioNotExistException:
            return "new"
        sidecar = self._mgr.scenario_root / name / SIDECAR_NAME
        if not sidecar.is_file():
            return "foreign"
        try:
            payload = json.loads(sidecar.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return "foreign"
        if payload.get("compose_sha256") != _sha256(compose_text):
            return "foreign"
        return "ours"

    # -- save ------------------------------------------------------------------

    def save(self, design: ScenarioDesign, *, overwrite: bool = False) -> list[str]:
        """Write the design as a real scenario; return self-check warnings.

        :raises AdminError: On design errors (bad networks, no services).
        :raises ScenarioExistException: When the target exists and ``overwrite``
            is not set (the UI resolves collisions before retrying).
        """
        if not design.blocks:
            raise AdminError("Add at least one service before saving the scenario.")
        network_errors = design.invalid_networks()
        if network_errors:
            raise AdminError("; ".join(network_errors))

        compose_text = export_compose_preview(design)
        sidecar = json.dumps(
            {
                "version": SIDECAR_VERSION,
                "compose_sha256": _sha256(compose_text),
                "design": design.model_dump(mode="json"),
            },
            indent=2,
        )
        self._mgr.save_scenario_files(
            design.name,
            compose_text,
            volume_files=design.volume_files(),
            extra_files={SIDECAR_NAME: sidecar},
            overwrite=overwrite,
        )
        return self._self_check(design)

    def _self_check(self, design: ScenarioDesign) -> list[str]:
        """Diff what the written templates require against the design's promise."""
        warnings: list[str] = []
        scaffold = self._mgr.fetch_variables(design.name)
        for block in design.blocks:
            svc = scaffold.get(block.service_key, {})
            promised_ports = set(block.ports)
            promised_env = set(block.env_keys)
            promised_volumes = {slot.name for slot in block.volumes}
            if set(svc.get("port_map", {})) != promised_ports:
                warnings.append(
                    f"service '{block.label}': template ports {sorted(svc.get('port_map', {}))} "
                    f"differ from design {sorted(promised_ports)}"
                )
            if set(svc.get("env_map", {})) != promised_env:
                warnings.append(f"service '{block.label}': template env keys differ from design")
            if set(svc.get("volume_map", {})) != promised_volumes:
                warnings.append(f"service '{block.label}': template volumes differ from design")
        required_secrets = set(self._mgr.fetch_secret_keys(design.name))
        promised_secrets = set(design.secrets)
        for name in sorted(promised_secrets - required_secrets):
            warnings.append(
                f"secret '{name}' is declared in the design but no volume template "
                f"references secret_map__{name} — it will not be required at assignment"
            )
        for name in sorted(required_secrets - promised_secrets):
            warnings.append(
                f"volume templates reference secret_map__{name}, which is not declared "
                "in the design"
            )
        return warnings

    # -- load ------------------------------------------------------------------

    def load(self, name: str) -> DesignerLoadResult:
        """Sidecar-first load; fall back to the best-effort importer."""
        compose_text = self._mgr.read_compose_template(name)
        state = self.collision_state(name)
        if state == "ours":
            sidecar = self._mgr.scenario_root / name / SIDECAR_NAME
            payload = json.loads(sidecar.read_text(encoding="utf-8"))
            design = ScenarioDesign.model_validate(payload["design"])
            return DesignerLoadResult(design, compose_text, "sidecar")
        # foreign or hand-edited: best-effort import, may lose detail
        from fit_ctf_admin.scenario.compose_import import ScenarioComposeImporter

        try:
            design = ScenarioComposeImporter.import_scenario_dir(
                self._mgr.get_scenario_dir(name), merge_admin_design=False
            )
            design.name = name
            return DesignerLoadResult(design, compose_text, "imported")
        except Exception:
            return DesignerLoadResult(None, compose_text, "raw")
