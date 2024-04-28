from __future__ import annotations

import fit_ctf_db_models.user as _user
import fit_ctf_db_models.user_config as _user_config
import json
import logging
import os
import shutil
import subprocess
import sys

from bson import ObjectId
from dataclasses import asdict, dataclass, field
from distutils.dir_util import copy_tree
from fit_ctf_backend import ProjectNotExistsException, DirNotEmptyException
from fit_ctf_db_models.base import BaseManager, Base
from fit_ctf_db_models.network import Network
from fit_ctf_templates import TEMPLATE_DIRNAME
from fit_ctf_utils import get_template
from pathlib import Path
from pymongo.database import Database
from typing import Any

log = logging.getLogger()
CURR_FILE = os.path.realpath(__file__)


@dataclass
class Project(Base):
    name: str
    config_root_dir: str
    compose_file: str
    volume_mount_root_dir: str
    networks: list[Network] = field(default_factory=list)
    description: str = ""

    @property
    def _compose_filepath(self) -> Path:
        return Path(self.config_root_dir) / self.compose_file

    def start(self) -> subprocess.CompletedProcess:
        """Boot the project server.

        Run `podman-compose up` in the sub-shell.

        Returns:
            subprocess.CompletedProcess: Command call results.
        """
        cmd = f"podman-compose -f {self._compose_filepath} up -d"
        proc = subprocess.run(
            cmd.split(),
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
        return proc

    def stop(self) -> subprocess.CompletedProcess:
        """Stop the project server.

        Run `podman-compose down` in the sub-shell.

        Returns:
            subprocess.CompletedProcess: Command call results.
        """
        cmd = f"podman-compose -f {self._compose_filepath} down"
        proc = subprocess.run(
            cmd.split(),
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
        return proc

    def is_running(self) -> bool:
        """Check if the project server is running.

        Returns:
            bool: Returns `True` if the server is running; `False` otherwise.
        """
        cmd = f'podman ps -a --format=json --filter=name=^{self.name}'
        proc = subprocess.run(
            cmd.split(),
            capture_output=True,
            text=True
        )
        data = json.loads(proc.stdout)
        return len(data) > 0

    def build(self) -> subprocess.CompletedProcess:
        """Rebuild project images.

        Run `podman-compose down` in the sub-shell.

        Returns:
            subprocess.CompletedProcess: Command call results.
        """

        cmd = f"podman-compose -f {self._compose_filepath} build"
        proc = subprocess.run(
            cmd.split(),
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
        return proc

    def printable_format(self):
        # TODO:
        return f"{self.name} {self.config_root_dir} {self.description}"


class ProjectManager(BaseManager[Project]):
    def __init__(self, db: Database):
        super().__init__(db, db["project"])

    def get_doc_by_id(self, _id: ObjectId) -> Project | None:
        res = self._coll.find_one({"_id": _id})
        return Project(**res) if res else None

    def get_doc_by_id_raw(self, _id: ObjectId):
        return self._coll.find_one({"_id": _id})

    def get_doc_by_filter(self, **kw) -> Project | None:
        res = self._coll.find_one(filter=kw)
        return Project(**res) if res else None

    def get_docs(self, filter: dict[str, Any]) -> list[Project]:
        res = self._coll.find(filter=filter)
        return [Project(**data) for data in res]

    def create_and_insert_doc(self, **kw) -> Project:
        doc = Project(_id=ObjectId(), **kw)
        self.insert_doc(doc)
        return doc

    def get_project_info(self) -> dict[str, Any]:
        return {p.name: p for p in self.get_docs({})}

    def get_active_users_for_project(self, project_name: str) -> list[_user.User]:
        """Return list of users that are assigned to the project."""
        project = self.get_doc_by_filter(name=project_name)
        if not project:
            raise ProjectNotExistsException(
                f"Project `{project_name}` does not exists."
            )

        uc_coll = _user_config.UserConfigManager(self._db).collection
        pipeline = [
            {
                # search only user_config for the given user
                "$match": {"project_id.$id": project.id}
            },
            {
                # get project info
                "$lookup": {
                    "from": "user",
                    "localField": "user_id.$id",
                    "foreignField": "_id",
                    "as": "user",
                }
            },
            {
                # since lookup returns array
                # pop the first element from the array
                "$unwind": "$user"
            },
            {"$project": {"user": 1, "_id": 0}},
        ]
        return [_user.User(**i["user"]) for i in uc_coll.aggregate(pipeline)]

    def init_project(
        self,
        name: str,
        dest_dir: str,
        volume_mount_root_dir: str,
        dir_name: str = "",
        description: str = "",
        compose_file: str = "server_compose.yaml",
    ) -> Project:
        """Create a project template."""
        # check if project already exists
        prj = self.get_doc_by_filter(name=name)
        if prj:
            return prj

        if not dir_name:
            dir_name = name.lower().replace(" ", "_")
        # append trailing slash
        destination = Path(dest_dir) / dir_name

        # create a destination directory
        os.makedirs(destination, exist_ok=True)
        if len(os.listdir(destination)) > 0:
            raise DirNotEmptyException(
                f"Destination directory `{destination}` is not empty"
            )

        os.makedirs(volume_mount_root_dir, exist_ok=True)

        # fill directory with templates
        template_dir = Path(TEMPLATE_DIRNAME)
        src_dir = template_dir / "server_project"
        copy_tree(str(src_dir), str(destination))

        # create server_compose.yaml file
        compose_filepath = destination / compose_file
        with open(str(compose_filepath), "w") as f:
            template = get_template("server_compose.yaml.j2", str(template_dir / "templates"))
            f.write(template.render(name=name))

        # store into the database
        prj = self.create_and_insert_doc(
            name=name,
            config_root_dir=str(destination),
            compose_file=compose_file,
            volume_mount_root_dir=str(volume_mount_root_dir),
            description=description,
        )

        return prj

    def delete_project(self, name: str) -> bool:
        """Delete a project."""
        # also deletes everything
        prj = self.get_doc_by_filter(name=name)
        if not prj:
            raise ProjectNotExistsException(f"Project `{name}` does not exists.")

        # stop project if running
        # TODO: enable in the future
        if prj.is_running():
            prj.stop()

        # TODO: remove built images

        # remove everything from the directory
        shutil.rmtree(prj.config_root_dir)
        return self.remove_doc_by_id(prj.id)

    def get_projects(self) -> list[str]:
        res = self._coll.find(filter={}, projection={"_id": 0, "name": 1})
        return [i["name"] for i in res]
