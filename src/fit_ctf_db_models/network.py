from __future__ import annotations

import re
import subprocess
import json

from typing import Any, Literal
from bson import ObjectId, DBRef
from dataclasses import dataclass
from fit_ctf_db_models.base import Base, BaseManager
from pymongo.database import Database


@dataclass
class Network(Base):
    parent_id: DBRef
    label_name: str
    network_name: str
    subnet: str = ""


class NetworkManager(BaseManager[Network]):
    def __init__(self, db: Database):
        super().__init__(db, db["network"])

    def get_doc_by_id(self, _id: ObjectId) -> Network | None:
        res = self._coll.find_one({"_id": _id})
        return Network(**res) if res else None

    def get_doc_by_id_raw(self, _id: ObjectId):
        return self._coll.find_one({"_id": _id})

    def get_doc_by_filter(self, **kw) -> Network | None:
        res = self._coll.find_one(filter=kw)
        return Network(**res) if res else None

    def get_docs(self, filter: dict[str, Any]) -> list[Network]:
        res = self._coll.find(filter=filter)
        return [Network(**data) for data in res]

    def create_network(
        self,
        label_name: str,
        network_name: str,
        parent_type: Literal["project", "user"],
        parent_id: ObjectId,
        subnet: str = "",
    ):
        create_net_cmd = ["podman", "network", "create"]
        if subnet and re.match(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/\d{1,2}", subnet):
            create_net_cmd += ["--subnet", subnet]
        create_net_cmd.append(network_name)
        res = subprocess.run(create_net_cmd, capture_output=True)

        if res.returncode > 0:
            raise Exception(res.stderr)

        raise NotImplemented()
