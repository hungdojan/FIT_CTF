"""Data models for the admin page scenario designer."""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

NameMode = Literal["random", "concrete"]
NAME_MODE_OPTIONS: list[tuple[str, str]] = [
    ("Random", "random"),
    ("Concrete", "concrete"),
]

BUILTIN_NETWORKS: tuple[str, ...] = ("shared", "private", "operational")
BUILTIN_NETWORK_LABELS: dict[str, str] = {
    "shared": "Shared",
    "private": "Private",
    "operational": "Operational",
}

BLOCK_WIDTH = 16
BLOCK_HEIGHT = 3
BLOCK_WIDTH_EXPANDED = 30
BLOCK_HEIGHT_EXPANDED = 10
GRID_SNAP = 2
WORLD_WIDTH = 120
WORLD_HEIGHT = 80

# Fallback module names when no module registry is reachable (preview mode);
# connected mode reads the real catalog via ``ModuleManager.list_modules``.
FALLBACK_MODULE_NAMES: tuple[str, ...] = ("template", "ssh_debian", "ssh_ubi")

TargetKind = Literal["user", "project"]
VolumeKind = Literal["path", "static", "template"]
# "module": built from modules/<name>; "image": pulled as-is (no build section)
ImageSource = Literal["module", "image"]
IMAGE_SOURCE_OPTIONS: list[tuple[str, str]] = [
    ("Module (built from modules/)", "module"),
    ("External image (pulled as-is)", "image"),
]
DEFAULT_IMAGE_REGISTRY = "docker.io"

_NETWORK_SLUG_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_SECRET_KEY_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_SERVICE_KEY_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_CONTAINER_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$")
_ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def snap_coordinate(value: int) -> int:
    return round(value / GRID_SNAP) * GRID_SNAP


def is_builtin_network(name: str) -> bool:
    return name in BUILTIN_NETWORKS


def network_jinja_key(name: str) -> str:
    if is_builtin_network(name):
        return f"network_map__{name}"
    return name


def normalize_secret_key(name: str) -> str:
    key = name.strip().lower().replace("-", "_")
    if not key or "__" in key or not _SECRET_KEY_RE.match(key):
        raise ValueError("Secret name must be a slug like flag_main (no '__').")
    return key


def normalize_env_key(name: str) -> str:
    key = name.strip()
    if not key or not _ENV_KEY_RE.match(key):
        raise ValueError("Env name must look like ADMIN or DB_HOST.")
    return key


def generate_service_key() -> str:
    return f"svc_{uuid.uuid4().hex[:6]}"


def generate_container_name() -> str:
    return f"ctr_{uuid.uuid4().hex[:6]}"


def normalize_image_ref(value: str) -> str:
    """Complete a short image reference the way the container engines do.

    ``nginx`` -> ``docker.io/library/nginx``, ``bitnami/nginx`` ->
    ``docker.io/bitnami/nginx``; anything that already names a registry
    (``ghcr.io/...``, ``localhost:5000/...``) is left alone.
    """
    ref = value.strip()
    if not ref:
        raise ValueError("Image reference is required (e.g. nginx:alpine).")
    if any(char.isspace() for char in ref):
        raise ValueError("Image reference cannot contain spaces.")
    if "/" not in ref:
        return f"{DEFAULT_IMAGE_REGISTRY}/library/{ref}"
    head = ref.split("/", 1)[0]
    is_registry = "." in head or ":" in head or head == "localhost"
    return ref if is_registry else f"{DEFAULT_IMAGE_REGISTRY}/{ref}"


def normalize_service_key(name: str) -> str:
    key = name.strip().lower().replace("-", "_")
    if not key or not _SERVICE_KEY_RE.match(key):
        raise ValueError("Service key must be a slug like challenge or svc_web.")
    return key


def normalize_container_name(name: str) -> str:
    value = name.strip()
    if not value or not _CONTAINER_NAME_RE.match(value):
        raise ValueError("Container name must look like my_container-1.")
    return value


class CustomNetwork(BaseModel):
    """User-defined network (e.g. extra private VLAN)."""

    name: str
    label: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        slug = value.strip().lower().replace("-", "_")
        if not _NETWORK_SLUG_RE.match(slug):
            raise ValueError("Network name must be a lowercase slug (e.g. db_private).")
        if slug in BUILTIN_NETWORKS:
            raise ValueError(f"'{slug}' is reserved for a built-in network.")
        return slug

    @field_validator("label")
    @classmethod
    def validate_label(cls, value: str) -> str:
        label = value.strip()
        if not label:
            raise ValueError("Network label cannot be empty.")
        return label


def network_label(name: str, custom_networks: list[CustomNetwork]) -> str:
    if is_builtin_network(name):
        return BUILTIN_NETWORK_LABELS[name]
    for network in custom_networks:
        if network.name == name:
            return network.label
    return name


class VolumeSlot(BaseModel):
    """One volume mount of a service.

    ``kind`` controls what the designer writes into the scenario directory:

    * ``path`` — nothing; the admin supplies ``src_path`` at assignment time.
    * ``static`` — ``volumes/<name>`` with ``body`` as-is.
    * ``template`` — ``volumes/<name>.template`` with ``body``; the body may
      reference ``{{ secret_map__<secret> }}`` and
      ``{{ <svc>__volume_map__<name>__<param> }}`` slots.
    """

    name: str
    container_path: str
    read_only: bool = True
    kind: VolumeKind = "path"
    body: str = ""

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        slug = value.strip().lower().replace("-", "_")
        if not _SERVICE_KEY_RE.match(slug):
            raise ValueError("Volume name must be a slug like cfg or flag_file.")
        return slug

    @field_validator("container_path")
    @classmethod
    def validate_container_path(cls, value: str) -> str:
        path = value.strip()
        if not path.startswith("/"):
            raise ValueError("Container path must be absolute (e.g. /data).")
        return path

    @property
    def file_name(self) -> str:
        """File name written under ``volumes/`` (template kind gets a suffix)."""
        return f"{self.name}.template" if self.kind == "template" else self.name


class ServiceBlock(BaseModel):
    """One draggable service block on the design canvas."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    label: str
    service_key: str
    service_key_mode: NameMode = "random"
    container_name: str | None = None
    container_name_mode: NameMode = "random"
    module_name: str = "template"
    image_source: ImageSource = "module"
    image_ref: str = ""
    x: int = 4
    y: int = 4
    networks: list[str] = Field(default_factory=lambda: ["shared"])
    ports: dict[str, int] = Field(default_factory=lambda: {"web": 8080})
    env_keys: list[str] = Field(default_factory=list)
    volumes: list[VolumeSlot] = Field(default_factory=list)

    @property
    def image_label(self) -> str:
        """What the service pulls/builds, for compact displays."""
        if self.image_source == "image":
            return self.image_ref or "(no image set)"
        return self.module_name

    def clamp_position(self, world_width: int, world_height: int) -> None:
        max_x = max(0, world_width - BLOCK_WIDTH)
        max_y = max(0, world_height - BLOCK_HEIGHT)
        self.x = max(0, min(snap_coordinate(self.x), max_x))
        self.y = max(0, min(snap_coordinate(self.y), max_y))


class ScenarioDesign(BaseModel):
    """Full scenario layout produced by the admin page.

    ``target_kind`` decides which compile-time variables the exported template
    may use: user-cluster scenarios get ``{{ username }}`` in their ``name:``
    line, project-cluster scenarios must not (project compiles only supply
    ``project_name``).
    """

    name: str = "new_scenario"
    target_kind: TargetKind = "user"
    secrets: list[str] = Field(default_factory=list)
    custom_networks: list[CustomNetwork] = Field(default_factory=list)
    blocks: list[ServiceBlock] = Field(default_factory=list)

    def all_network_names(self) -> list[str]:
        return [*BUILTIN_NETWORKS, *[n.name for n in self.custom_networks]]

    def add_custom_network(self, name: str, label: str) -> CustomNetwork:
        network = CustomNetwork(name=name, label=label)
        if network.name in self.all_network_names():
            raise ValueError(f"Network '{network.name}' already exists.")
        self.custom_networks.append(network)
        return network

    def remove_custom_network(self, name: str) -> bool:
        before = len(self.custom_networks)
        self.custom_networks = [n for n in self.custom_networks if n.name != name]
        for block in self.blocks:
            block.networks = [n for n in block.networks if n != name]
        return len(self.custom_networks) < before

    def add_secret(self, name: str) -> str:
        key = normalize_secret_key(name)
        if key in self.secrets:
            raise ValueError(f"Secret '{key}' already exists.")
        self.secrets.append(key)
        self.secrets.sort()
        return key

    def remove_secret(self, name: str) -> bool:
        if name not in self.secrets:
            return False
        self.secrets.remove(name)
        return True

    def add_block(self, label: str | None = None, module_name: str = "template") -> ServiceBlock:
        index = len(self.blocks) + 1
        block = ServiceBlock(
            label=label or f"service_{index}",
            service_key=self._unique_service_key(),
            module_name=module_name,
            x=4 + (index % 4) * (BLOCK_WIDTH + 2),
            y=4 + (index // 4) * (BLOCK_HEIGHT + 1),
        )
        self.blocks.append(block)
        return block

    def _unique_service_key(self) -> str:
        used = {block.service_key for block in self.blocks}
        for _ in range(100):
            key = generate_service_key()
            if key not in used:
                return key
        raise ValueError("Could not generate a unique service key.")

    def _unique_container_name(self) -> str:
        used = {block.container_name for block in self.blocks if block.container_name is not None}
        for _ in range(100):
            name = generate_container_name()
            if name not in used:
                return name
        raise ValueError("Could not generate a unique container name.")

    def regenerate_service_key(self, block_id: str) -> str:
        block = self.get_block(block_id)
        if block is None:
            raise ValueError("No service selected.")
        used = {b.service_key for b in self.blocks if b.id != block_id}
        for _ in range(100):
            key = generate_service_key()
            if key not in used:
                block.service_key = key
                return key
        raise ValueError("Could not generate a unique service key.")

    def set_service_key(self, block_id: str, key: str) -> str:
        block = self.get_block(block_id)
        if block is None:
            raise ValueError("No service selected.")
        service_key = normalize_service_key(key)
        for other in self.blocks:
            if other.id != block_id and other.service_key == service_key:
                raise ValueError(f"Service key '{service_key}' is already used.")
        block.service_key = service_key
        return service_key

    def set_container_name(self, block_id: str, name: str | None) -> str | None:
        block = self.get_block(block_id)
        if block is None:
            raise ValueError("No service selected.")
        if name is None or not name.strip():
            block.container_name = None
            return None
        container_name = normalize_container_name(name)
        for other in self.blocks:
            if (
                other.id != block_id
                and other.container_name_mode == "concrete"
                and other.container_name == container_name
            ):
                raise ValueError(f"Container name '{container_name}' is already used.")
        block.container_name = container_name
        return container_name

    def remove_block(self, block_id: str) -> bool:
        before = len(self.blocks)
        self.blocks = [b for b in self.blocks if b.id != block_id]
        return len(self.blocks) < before

    def get_block(self, block_id: str) -> ServiceBlock | None:
        return next((b for b in self.blocks if b.id == block_id), None)

    def add_env_to_block(self, block_id: str, key: str) -> None:
        block = self.get_block(block_id)
        if block is None:
            raise ValueError("No service selected.")
        env_key = normalize_env_key(key)
        if env_key in block.env_keys:
            raise ValueError(f"Env var '{env_key}' already exists.")
        block.env_keys.append(env_key)
        block.env_keys.sort()

    def remove_env_from_block(self, block_id: str, key: str) -> bool:
        block = self.get_block(block_id)
        if block is None:
            return False
        if key not in block.env_keys:
            return False
        block.env_keys.remove(key)
        return True

    def volume_files(self) -> dict[str, str]:
        """Files to write under ``volumes/`` (static and template slots)."""
        files: dict[str, str] = {}
        for block in self.blocks:
            for slot in block.volumes:
                if slot.kind in ("static", "template"):
                    files[slot.file_name] = slot.body
        return files

    def invalid_networks(self) -> list[str]:
        """Built-in networks the target kind cannot compile.

        User clusters render with ``shared``+``private`` network maps, project
        clusters with ``shared``+``operational``.
        """
        forbidden = "operational" if self.target_kind == "user" else "private"
        errors = []
        for block in self.blocks:
            if forbidden in block.networks:
                errors.append(
                    f"service '{block.label}' uses the '{forbidden}' network, which is "
                    f"not available on {self.target_kind} clusters"
                )
        return errors

    def to_json(self) -> str:
        return json.dumps(self.model_dump(mode="json"), indent=2)

    @classmethod
    def from_json(cls, raw: str) -> ScenarioDesign:
        return cls.model_validate(json.loads(raw))

    def save(self, path: Path) -> None:
        path.write_text(self.to_json(), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> ScenarioDesign:
        return cls.from_json(path.read_text(encoding="utf-8"))

    def model_post_init(self, __context: Any) -> None:
        for block in self.blocks:
            block.x = snap_coordinate(block.x)
            block.y = snap_coordinate(block.y)


def parse_key_value_lines(raw: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key:
            result[key] = value.strip()
    return result


def parse_port_lines(raw: str) -> dict[str, int]:
    result: dict[str, int] = {}
    for chunk in raw.replace("\n", ",").split(","):
        chunk = chunk.strip()
        if not chunk or ":" not in chunk:
            continue
        name, _, port_text = chunk.partition(":")
        name = name.strip()
        try:
            port = int(port_text.strip())
        except ValueError:
            continue
        if name and 1 <= port <= 65_535:
            result[name] = port
    return result


def format_key_value_lines(data: dict[str, str]) -> str:
    return "\n".join(f"{key}={value}" for key, value in sorted(data.items()))


def format_port_lines(data: dict[str, int]) -> str:
    return ", ".join(f"{name}:{port}" for name, port in sorted(data.items()))


def format_ports_compact(data: dict[str, int], max_items: int = 3) -> str:
    if not data:
        return "—"
    items = sorted(data.items())[:max_items]
    text = ", ".join(f"{name}:{port}" for name, port in items)
    if len(data) > max_items:
        text += ", …"
    return text


def format_env_compact(keys: list[str], max_items: int = 2) -> str:
    if not keys:
        return "—"
    items = sorted(keys)[:max_items]
    text = ", ".join(items)
    if len(keys) > max_items:
        text += ", …"
    return text
