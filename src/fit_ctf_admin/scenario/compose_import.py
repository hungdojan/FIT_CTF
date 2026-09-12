"""Import FIT-CTF scenario compose templates into admin page designs."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from fit_ctf_admin.scenario.design_model import (
    BLOCK_HEIGHT,
    BLOCK_WIDTH,
    WORLD_HEIGHT,
    WORLD_WIDTH,
    CustomNetwork,
    ScenarioDesign,
    ServiceBlock,
    is_builtin_network,
    snap_coordinate,
)

COMPOSE_TEMPLATE_NAME = "scenario_compose.yaml.j2"
ADMIN_DESIGN_NAME = "admin_design.json"

_MACRO_BLOCK = re.compile(r"\{%-?\s*macro\b.*?endmacro\s*-?%}", re.DOTALL | re.IGNORECASE)
_JINJA_EXPR = re.compile(r"\{\{.*?\}\}")
_NETWORK_MAP_EXPR = re.compile(r"\{\{\s*(?:render_raw\(')?network_map__(\w+)(?:'\))?\s*\}\}")
_PATHS_MODULES = re.compile(r"\{\{\s*(?:render_raw\(')?paths__modules(?:'\))?\s*\}\}")
_PORT_SLOT = re.compile(r'"?\{\{?\s*(\w+)__port_map__(\w+)\s*\}\}?"?\s*:\s*"?(\d+)"?')
_ENV_SLOT = re.compile(r'"([A-Za-z_][A-Za-z0-9_]*)=\{\{?\s*(\w+)__env_map__(\w+)\s*\}\}?"')
_MODULE_CONTEXT = re.compile(
    r"context:\s*[^\n]*/([A-Za-z0-9_-]+)\s*$",
    re.MULTILINE,
)
_MODULE_DEFAULT = re.compile(r'default\("([A-Za-z0-9_-]+)"\)')
_MODULE_IMAGE = re.compile(r"image:\s*fit-ctf/([A-Za-z0-9_-]+):latest")
_NAME_LINE = re.compile(r"^name:\s*(.+)$", re.MULTILINE)
_SERVICE_KEY_RE = re.compile(r"^[a-z][a-z0-9_]*$")


class ScenarioComposeImporter:
    """Build a :class:`ScenarioDesign` from ``scenario_compose.yaml.j2``."""

    def __init__(self, *, path: Path | None = None, text: str | None = None) -> None:
        if (path is None) == (text is None):
            raise ValueError("Provide exactly one of path= or text=.")
        if path is not None:
            self.path = path
            self.text = path.read_text(encoding="utf-8")
        else:
            self.path = None
            self.text = text or ""

    @classmethod
    def from_scenario_dir(
        cls,
        scenario_dir: Path,
        *,
        compose_name: str = COMPOSE_TEMPLATE_NAME,
    ) -> ScenarioComposeImporter:
        compose_path = scenario_dir / compose_name
        if not compose_path.is_file():
            raise FileNotFoundError(f"No compose template at {compose_path}")
        return cls(path=compose_path)

    @classmethod
    def import_scenario_dir(
        cls,
        scenario_dir: Path,
        *,
        merge_admin_design: bool = True,
        compose_name: str = COMPOSE_TEMPLATE_NAME,
    ) -> ScenarioDesign:
        """Import compose template, optionally merging canvas layout from admin JSON."""
        importer = cls.from_scenario_dir(scenario_dir, compose_name=compose_name)
        design = importer.import_design(scenario_name_fallback=scenario_dir.name)
        if merge_admin_design:
            overlay_path = scenario_dir / ADMIN_DESIGN_NAME
            if overlay_path.is_file():
                design = cls.merge_layout_overlay(design, overlay_path)
        return design

    @staticmethod
    def merge_layout_overlay(design: ScenarioDesign, overlay_path: Path) -> ScenarioDesign:
        """Apply display names and canvas positions from a saved admin design."""
        overlay = ScenarioDesign.load(overlay_path)
        by_key = {block.service_key: block for block in overlay.blocks}
        for block in design.blocks:
            saved = by_key.get(block.service_key)
            if saved is None:
                continue
            block.label = saved.label
            block.x = saved.x
            block.y = saved.y
        if overlay.secrets:
            design.secrets = list(overlay.secrets)
        return design

    def import_design(self, scenario_name_fallback: str = "new_scenario") -> ScenarioDesign:
        document = self._load_document()
        scenario_name = self._extract_scenario_name(scenario_name_fallback)
        custom_networks = self._extract_custom_networks(document)
        blocks = self._extract_blocks(document)
        self._auto_layout(blocks)
        return ScenarioDesign(
            name=scenario_name,
            custom_networks=custom_networks,
            blocks=blocks,
        )

    def _load_document(self) -> dict:
        prepared = self._prepare_yaml(self.text)
        loaded = yaml.safe_load(prepared)
        if not isinstance(loaded, dict):
            raise ValueError("Compose template must parse to a YAML mapping.")
        return loaded

    def _prepare_yaml(self, text: str) -> str:
        without_macros = _MACRO_BLOCK.sub("", text)
        normalized = _PATHS_MODULES.sub("MODULES", without_macros)
        normalized = _NETWORK_MAP_EXPR.sub(
            lambda match: f"net_{match.group(1)}",
            normalized,
        )
        lines: list[str] = []
        for line in normalized.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if not stripped:
                lines.append("")
                continue
            cleaned = _JINJA_EXPR.sub("null", line)
            if cleaned.strip() in {"null:", "null"}:
                continue
            lines.append(cleaned)
        return "\n".join(lines)

    def _extract_scenario_name(self, fallback: str) -> str:
        match = _NAME_LINE.search(self.text)
        if match is None:
            return fallback
        raw = match.group(1).strip().strip("\"'")
        suffixes = re.findall(r"_([a-z][a-z0-9_]*)", raw)
        if suffixes:
            return suffixes[-1]
        without_jinja = _JINJA_EXPR.sub("", raw).strip("_")
        return without_jinja or fallback

    def _extract_custom_networks(self, document: dict) -> list[CustomNetwork]:
        networks = document.get("networks")
        if not isinstance(networks, dict):
            return []
        custom: list[CustomNetwork] = []
        for key in networks:
            resolved = self._resolve_network_name(str(key))
            if resolved is None or is_builtin_network(resolved):
                continue
            custom.append(CustomNetwork(name=resolved, label=resolved.replace("_", " ").title()))
        return custom

    def _extract_blocks(self, document: dict) -> list[ServiceBlock]:
        services = document.get("services")
        if not isinstance(services, dict):
            return []
        blocks: list[ServiceBlock] = []
        for service_key, raw_service in services.items():
            if not isinstance(raw_service, dict):
                continue
            key = str(service_key)
            section = self._service_section_text(key)
            module_name, image_source, image_ref = self._extract_image(section, raw_service)
            blocks.append(
                ServiceBlock(
                    label=key,
                    service_key=key,
                    service_key_mode="concrete",
                    module_name=module_name,
                    image_source=image_source,
                    image_ref=image_ref,
                    networks=self._extract_service_networks(raw_service),
                    ports=self._extract_ports(section, key),
                    env_keys=self._extract_env_keys(section, key),
                    container_name=self._extract_container_name(raw_service),
                    container_name_mode=(
                        "concrete" if raw_service.get("container_name") else "random"
                    ),
                )
            )
        return blocks

    def _service_section_text(self, service_key: str) -> str:
        pattern = re.compile(
            rf"^  {re.escape(service_key)}:\n(.*?)(?=^  \w+:|^networks:|\Z)",
            re.MULTILINE | re.DOTALL,
        )
        match = pattern.search(self.text)
        return match.group(0) if match else ""

    def _extract_image(self, section: str, service: dict) -> tuple[str, str, str]:
        """Return ``(module_name, image_source, image_ref)`` for one service.

        A service that only carries an ``image:`` which is not a locally built
        ``fit-ctf/<module>`` one is treated as an external image, so designs
        using off-the-shelf images survive a round-trip through the importer.
        """
        default_match = _MODULE_DEFAULT.search(section)
        if default_match:
            return default_match.group(1), "module", ""
        context_match = _MODULE_CONTEXT.search(section)
        if context_match:
            return context_match.group(1), "module", ""
        image = service.get("image")
        if isinstance(image, str):
            image_match = _MODULE_IMAGE.search(f"image: {image}")
            if image_match:
                return image_match.group(1), "module", ""
            reference = image.strip()
            if reference and not _JINJA_EXPR.search(reference):
                return "template", "image", reference
        return "template", "module", ""

    def _extract_service_networks(self, service: dict) -> list[str]:
        networks = service.get("networks")
        if not isinstance(networks, dict):
            return ["shared"]
        resolved = [
            name
            for name in (self._resolve_network_name(str(key)) for key in networks)
            if name is not None
        ]
        return resolved or ["shared"]

    def _extract_ports(self, section: str, service_key: str) -> dict[str, int]:
        ports: dict[str, int] = {}
        for match in _PORT_SLOT.finditer(section):
            slot_service, port_name, container_port = match.groups()
            if slot_service != service_key:
                continue
            ports[port_name] = int(container_port)
        return ports

    def _extract_env_keys(self, section: str, service_key: str) -> list[str]:
        keys: list[str] = []
        for match in _ENV_SLOT.finditer(section):
            env_name, slot_service, slot_key = match.groups()
            if slot_service != service_key or env_name != slot_key:
                continue
            keys.append(env_name)
        return sorted(set(keys))

    def _extract_container_name(self, service: dict) -> str | None:
        value = service.get("container_name")
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None

    def _resolve_network_name(self, key: str) -> str | None:
        cleaned = key.strip().strip("\"'")
        if cleaned in ("null", ""):
            return None
        if cleaned.startswith("net_"):
            builtin = cleaned.removeprefix("net_")
            if is_builtin_network(builtin):
                return builtin
        network_match = re.fullmatch(r"network_map__(\w+)", cleaned)
        if network_match:
            return network_match.group(1)
        if is_builtin_network(cleaned):
            return cleaned
        if _SERVICE_KEY_RE.match(cleaned):
            return cleaned
        return None

    def _auto_layout(self, blocks: list[ServiceBlock]) -> None:
        for index, block in enumerate(blocks):
            block.x = snap_coordinate(4 + (index % 4) * (BLOCK_WIDTH + 2))
            block.y = snap_coordinate(4 + (index // 4) * (BLOCK_HEIGHT + 1))
            block.clamp_position(WORLD_WIDTH, WORLD_HEIGHT)
