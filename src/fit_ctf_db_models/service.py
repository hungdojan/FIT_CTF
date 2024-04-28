from __future__ import annotations
from dataclasses import dataclass, field
from fit_ctf_db_models.compose_objects import Ports, Volume
from fit_ctf_db_models.network import Network

@dataclass
class Service:
    name: str
    build_dir: str
    volumes: list[Volume]
    networks: list[Network]
    ports: list[Ports]
