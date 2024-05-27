from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import zipfile
from dataclasses import dataclass, field, fields
from distutils.dir_util import copy_tree
from pathlib import Path
from typing import Any

from bson import ObjectId
from pymongo.database import Database

import fit_ctf_db_models.user as _user
import fit_ctf_db_models.user_config as _user_config
from fit_ctf_backend import DirNotEmptyException, ProjectNotExistsException
from fit_ctf_backend.constants import (
    DEFAULT_MODULE_BUILD_DIRNAME,
    DEFAULT_MODULE_COMPOSE_NAME,
    DEFAULT_STARTING_PORT,
)
from fit_ctf_backend.exceptions import DirNotExistsException
from fit_ctf_db_models.base import Base, BaseManager
from fit_ctf_db_models.compose_objects import Module
from fit_ctf_templates import TEMPLATE_DIRNAME, TEMPLATE_FILES, get_template
from fit_ctf_utils.podman_utils import (
    podman_compose_down,
    podman_compose_up,
    podman_ps,
    podman_rm_networks,
    podman_stats,
)

log = logging.getLogger()
CURR_FILE = os.path.realpath(__file__)


@dataclass(init=False)
class Project(Base):
    name: str
    config_root_dir: str
    volume_mount_dirname: str
    compose_file: str
    max_nof_users: int
    starting_port_bind: int
    description: str = field(default="")
    active: bool = field(default=True)
    modules: dict[str, Module] = field(default_factory=dict)

    def __init__(self, **kwargs):
        # set default values
        self.description = ""
        self.active = True
        self.modules = dict()
        # ignore extra fields
        names = set([f.name for f in fields(self)])
        for k, v in kwargs.items():
            if k in names:
                setattr(self, k, v)

    @property
    def _compose_filepath(self) -> Path:
        return Path(self.config_root_dir) / self.compose_file

    def start(self) -> subprocess.CompletedProcess:
        """Boot the project server.

        Run `podman-compose up` in the sub-shell.

        Returns:
            subprocess.CompletedProcess: Command call results.
        """
        return podman_compose_up(str(self._compose_filepath))

    def restart(self):
        """Restart project server.

        Run `podman-compose up` in the sub-shell.

        Returns:
            subprocess.CompletedProcess: Command call results.
        """
        self.stop()
        self.start()

    def stop(self) -> subprocess.CompletedProcess:
        """Stop the project server.

        Run `podman-compose down` in the sub-shell.

        Returns:
            subprocess.CompletedProcess: Command call results.
        """
        return podman_compose_down(str(self._compose_filepath))

    def is_running(self) -> bool:
        """Check if the project server is running.

        Returns:
            bool: Returns `True` if the server is running; `False` otherwise.
        """
        cmd = f"podman ps -a --format=json --filter=name=^{self.name}"
        proc = subprocess.run(cmd.split(), capture_output=True, text=True)
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

    @property
    def _uc_mgr(self):
        return _user_config.UserConfigManager(self._db)

    def get_doc_by_id(self, _id: ObjectId) -> Project | None:
        res = self._coll.find_one({"_id": _id})
        return Project(**res) if res else None

    def get_doc_by_id_raw(self, _id: ObjectId):
        return self._coll.find_one({"_id": _id})

    def get_doc_by_filter(self, **kw) -> Project | None:
        res = self._coll.find_one(filter=kw)
        return Project(**res) if res else None

    def get_docs(self, **filter) -> list[Project]:
        res = self._coll.find(filter=filter)
        return [Project(**data) for data in res]

    def create_and_insert_doc(self, **kw) -> Project:
        doc = Project(_id=ObjectId(), **kw)
        self.insert_doc(doc)
        return doc

    def get_project_info(self) -> dict[str, Any]:
        return {p.name: p for p in self.get_docs()}

    def get_project(self, name: str) -> Project:
        prj = self.get_doc_by_filter(name=name, active=True)
        if not prj:
            raise ProjectNotExistsException(f"Project `{name}` does not exists.")
        return prj

    def get_active_users_for_project(
        self, project_or_name: str | Project
    ) -> list[_user.User]:
        """Return list of users that are assigned to the project."""
        project = project_or_name
        if not isinstance(project, Project):
            project = self.get_project(project)

        uc_coll = self._uc_mgr.collection
        pipeline = [
            {
                # search only user_config for the given user
                "$match": {"project_id.$id": project.id, "active": True}
            },
            {
                # get project info
                "$lookup": {
                    "from": "user",
                    "localField": "user_id.$id",
                    "foreignField": "_id",
                    "as": "user",
                    "pipeline": [
                        {"$match": {"active": True}},
                    ],
                }
            },
            {
                # since lookup returns array
                # pop the first element from the array
                "$unwind": "$user"
            },
        ]

        return [_user.User(**i["user"]) for i in uc_coll.aggregate(pipeline)]

    def get_active_users_for_project_raw(
        self, project_or_name: str | Project
    ) -> list[dict[str, Any]]:
        """Return list of users that are assigned to the project."""
        project = project_or_name
        if not isinstance(project, Project):
            project = self.get_project(project)

        uc_coll = self._uc_mgr.collection
        pipeline = [
            {
                # search only user_config for the given user
                "$match": {"project_id.$id": project.id, "active": True}
            },
            {
                "$lookup": {
                    "from": "project",
                    "localField": "project_id.$id",
                    "foreignField": "_id",
                    "pipeline": [{"$project": {"config_root_dir": 1, "_id": 0}}],
                    "as": "project",
                }
            },
            {
                # get project info
                "$lookup": {
                    "from": "user",
                    "localField": "user_id.$id",
                    "foreignField": "_id",
                    "as": "user",
                    "pipeline": [
                        {"$match": {"active": True}},
                        {"$project": {"password": 0, "shadow_hash": 0}},
                    ],
                }
            },
            {
                # since lookup returns array
                # pop the first element from the array
                "$unwind": "$user"
            },
            {"$unwind": "$project"},
            {
                "$project": {
                    "user": 1,
                    "_id": 0,
                    "forwarded_port": 1,
                    "mount": {
                        "$concat": ["$project.config_root_dir", "/", "$user.username"]
                    },
                }
            },
        ]

        return [
            #   vvvvvvvvvvvv -- spreading dict key-values
            {**i["user"], "mount": i["mount"], "forwarded_port": i["forwarded_port"]}
            for i in uc_coll.aggregate(pipeline)
        ]

    def _get_avaiable_starting_port(self) -> int:
        lof_prjs_cur = self._coll.find(
            filter={"active": True},
            projection={"_id": 0, "max_nof_users": 1, "starting_port_bind": 1},
        ).sort({"starting_port_bind": -1})
        lof_prjs = [i for i in lof_prjs_cur]
        if not lof_prjs:
            return DEFAULT_STARTING_PORT
        return lof_prjs[0]["starting_port_bind"] + lof_prjs[0]["max_nof_users"] + 1000

    def get_reserved_ports(self) -> list[dict[str, Any]]:
        pipeline = [
            {"$match": {"active": True}},
            {
                "$project": {
                    "_id": 1,
                    "name": 1,
                    "min_port": "$starting_port_bind",
                    "max_port": {"$add": ["$max_nof_users", "$starting_port_bind"]},
                }
            },
        ]
        return [i for i in self._coll.aggregate(pipeline)]

    def init_project(
        self,
        name: str,
        dest_dir: str,
        max_nof_users: int,
        starting_port_bind: int = -1,
        volume_mount_dirname: str = "_mounts",
        dir_name: str = "",
        description: str = "",
        compose_file: str = "server_compose.yaml",
    ) -> Project:
        """Create a project template.
        This function creates the following file structure:
            <dest_dir>
              -- <dir_name>
                  -- <compose_file>
                  -- <server_config>
                  -- _mounts
                      -- <home_volumes_for_each_user>
        """
        # check if project already exists
        prj = self.get_doc_by_filter(name=name)
        if prj:
            return prj
        if not os.path.isdir(dest_dir):
            raise DirNotExistsException("A destination directory does not exists.")

        if starting_port_bind < 0:
            starting_port_bind = self._get_avaiable_starting_port()

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

        volume_mount_dirpath = destination / volume_mount_dirname
        os.makedirs(volume_mount_dirpath, exist_ok=True)

        # fill directory with templates
        template_dir = Path(TEMPLATE_DIRNAME)
        src_dir = template_dir / "server_project"
        copy_tree(str(src_dir), str(destination))

        # create server_compose.yaml file
        compose_filepath = destination / compose_file
        with open(str(compose_filepath), "w") as f:
            template = get_template(TEMPLATE_FILES["server_compose"])
            f.write(template.render(name=name))

        # store into the database
        prj = self.create_and_insert_doc(
            name=name,
            config_root_dir=str(destination.resolve()),
            compose_file=compose_file,
            max_nof_users=max_nof_users,
            starting_port_bind=starting_port_bind,
            description=description,
            volume_mount_dirname=volume_mount_dirname,
            modules={},
        )

        return prj

    def generate_port_forwarding_script(
        self, project_name: str, dest_ip_addr: str, filename: str
    ):
        prj = self.get_project(project_name)
        lof_user_configs = self._uc_mgr.get_docs_raw(
            filter={"project_id.$id": prj.id, "active": True},
            projection={"_id": 0, "ssh_port": 1, "forwarded_port": 1},
        )

        lof_cmd = [
            "firewall-cmd --zone=public "
            "--add-forward-port="
            f"port={i['forwarded_port']}:"
            "proto=tcp:"
            f"toport={i['ssh_port']}:"
            f"toaddr={dest_ip_addr}\n"
            for i in lof_user_configs
        ]

        with open(filename, "w") as f:
            f.write("#!/usr/bin/env bash\n\n")
            f.writelines(lof_cmd)
            f.write("firewall-cmd --zone=public --add-masquerade\n")
        os.chmod(filename, 755)

    def print_resource_usage(self, project_name: str):
        prj = self.get_project(project_name)
        podman_stats(prj.name)

    def print_ps(self, project_name: str):
        prj = self.get_project(project_name)
        podman_ps(prj.name)

    def export_project(self, project_name: str, output_file: str):
        prj = self.get_project(project_name)
        with zipfile.ZipFile(output_file, "w", zipfile.ZIP_DEFLATED) as zf:
            # this code snippet originates from: https://stackoverflow.com/a/46604244
            for dirpath, _, filenames in os.walk(prj.config_root_dir):
                for filename in filenames:

                    # Write the file named filename to the archive,
                    # giving it the archive name 'arcname'.
                    filepath = os.path.join(dirpath, filename)
                    parentpath = os.path.relpath(filepath, prj.config_root_dir)
                    arcname = os.path.join(
                        os.path.basename(prj.config_root_dir), parentpath
                    )

                    zf.write(filepath, arcname)

    def delete_project(self, project_name: str):
        """Delete a project."""
        # also deletes everything
        prj = self.get_project(project_name)

        # stop project if running
        if prj.is_running():
            prj.stop()

        # unfollow all users
        self._uc_mgr.stop_all_user_instances(prj)
        self._uc_mgr.unassign_all_from_project(prj)

        podman_rm_networks(f"{prj.name}_")

        # remove everything from the directory
        shutil.rmtree(prj.config_root_dir)
        prj.active = False
        self.update_doc(prj)

    def get_projects(self, ignore_inactive: bool = False) -> list[dict[str, Any]]:
        _filter = {}
        if not ignore_inactive:
            _filter["active"] = True

        res = self._coll.aggregate(
            [
                {"$match": _filter},
                {
                    "$lookup": {
                        "from": "user_config",
                        "localField": "_id",
                        "foreignField": "project_id.$id",
                        "as": "user_configs",
                        "pipeline": [{"$match": {"active": True}}],
                    }
                },
                {
                    "$project": {
                        "_id": 0,
                        "name": 1,
                        "max_nof_users": 1,
                        "active_users": {"$size": "$user_configs"},
                        "active": 1,
                    }
                },
            ]
        )
        return [i for i in res]

    # MANAGE MODULES

    def create_module(self, project_name: str, module_name: str):
        project = self.get_project(project_name)

        # create a destination directory and check if exists
        module_root_dir = Path(project.config_root_dir) / "_modules" / module_name
        os.makedirs(module_root_dir, exist_ok=True)
        if len(os.listdir(module_root_dir)) > 0:
            raise DirNotEmptyException(
                f"Destination directory `{module_root_dir}` is not empty."
            )

        # fill directory with templates
        template_dir = Path(TEMPLATE_DIRNAME)
        src_dir = template_dir / "module"
        copy_tree(str(src_dir), str(module_root_dir))

        module = Module(
            name=module_name,
            module_root_dir=str(module_root_dir.resolve()),
            build_dir_name=DEFAULT_MODULE_BUILD_DIRNAME,
            compose_template_path=DEFAULT_MODULE_COMPOSE_NAME,
        )
        project.modules[module_name] = module

    def list_modules(self, project_name: str):
        project = self.get_project(project_name)
        return project.modules

    def remove_modules(self, project_name: str, module_name: str):
        project = self.get_project(project_name)

        if module_name not in project.modules:
            return

        # remove from all users
        lof_users = self.get_active_users_for_project(project)
        for user in lof_users:
            self._uc_mgr.remove_module(user, project, module_name)
