from __future__ import annotations

from bson import ObjectId, DBRef
from dataclasses import dataclass, field


@dataclass
class Volume:
    _id: ObjectId
    project_id: DBRef
    id_name: str
    volume_name: str
    external: bool = False
    driver: str = ""
    driver_opts: dict[str, str] = field(default_factory=dict)


@dataclass
class VolumeMount:
    host_volume: Volume | str
    container_dst: str
    opts: str = ""

    def __str__(self) -> str:
        host_name = self.host_volume
        if isinstance(self.host_volume, Volume):
            host_name = self.host_volume.id_name
        _s = f"{host_name}:{self.container_dst}"
        if self.opts:
            _s += self.opts
        return _s


@dataclass
class Ports:
    container_port: int
    host_port: int

    def __str__(self) -> str:
        return f"{self.container_port}:{self.host_port}"