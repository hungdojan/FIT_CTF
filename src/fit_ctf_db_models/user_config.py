from __future__ import annotations

import logging
import os
import shutil
import subprocess
from dataclasses import asdict, dataclass, field, fields
from distutils import sys
from pathlib import Path
from subprocess import Popen
from typing import Any

from bson import DBRef, ObjectId
from pymongo.database import Database

import fit_ctf_db_models.project as _project
import fit_ctf_db_models.user as _user
from fit_ctf_backend import (
    ProjectNotExistsException,
    SSHPortOutOfRangeException,
    UserNotAssignedToProjectException,
)
from fit_ctf_backend.exceptions import (
    MaxUserCountReachedException,
    ModuleExistsException,
    PortUsageCollisionException,
)
from fit_ctf_db_models.base import Base, BaseManager
from fit_ctf_db_models.compose_objects import Module
from fit_ctf_templates import TEMPLATE_FILES, get_template
from fit_ctf_utils.podman_utils import podman_get_networks, podman_rm_networks

log = logging.getLogger()


@dataclass(init=False)
class UserConfig(Base):
    _id: ObjectId
    user_id: DBRef
    project_id: DBRef
    ssh_port: int
    forwarded_port: int
    active: bool = field(default=True)
    modules: dict[str, Module] = field(default_factory=dict)

    def __init__(self, **kwargs):
        # set default values
        self.modules = dict()
        self.active = True

        # ignore extra fields
        names = set([f.name for f in fields(self)])
        for k, v in kwargs.items():
            if k in names:
                setattr(self, k, v)


class UserConfigManager(BaseManager[UserConfig]):
    def __init__(self, db: Database):
        super().__init__(db, db["user_config"])

    @property
    def _prj_mgr(self):
        return _project.ProjectManager(self._db)

    @property
    def _user_mgr(self):
        return _user.UserManager(self._db)

    def _multiple_users_pipeline(
        self, project: _project.Project, lof_usernames: list[str]
    ) -> list:
        return [
            {
                # get configs for a given project
                "$match": {"project_id.$id": project.id, "active": True}
            },
            {
                # get user info
                "$lookup": {
                    "from": "user",
                    "localField": "user_id.$id",
                    "foreignField": "_id",
                    "as": "user",
                    "pipeline": [
                        {
                            "$match": {
                                "active": True,
                                "username": {"$in": lof_usernames},
                            }
                        }
                    ],
                }
            },
            {
                # pop first element from the array
                "$unwind": "$user"
            },
            {
                # transform to the final internet format
                "$project": {
                    "username": "$user.username",
                }
            },
        ]

    def _all_users_pipeline(self, project: _project.Project) -> list:
        return [
            {
                # get configs for a given project
                "$match": {"project_id.$id": project.id, "active": True}
            },
            {
                # get user info
                "$lookup": {
                    "from": "user",
                    "localField": "user_id.$id",
                    "foreignField": "_id",
                    "as": "user",
                    "pipeline": [
                        {
                            "$match": {
                                "active": True,
                            }
                        }
                    ],
                }
            },
            {
                # pop first element from the array
                "$unwind": "$user"
            },
            {
                # transform to the final internet format
                "$project": {
                    "username": "$user.username",
                }
            },
        ]

    def _get_user_and_project(
        self, username: str, project_name: str
    ) -> tuple[_user.User, _project.Project]:
        user = self._user_mgr.get_user(username=username)
        project = self._prj_mgr.get_project(name=project_name)

        return user, project

    def _get_user(self, user_or_username: str | _user.User):
        user = user_or_username
        if not isinstance(user, _user.User):
            user = self._user_mgr.get_user(user)
        return user

    def _get_project(self, project_or_name: str | _project.Project):
        prj = project_or_name
        if not isinstance(prj, _project.Project):
            prj = self._prj_mgr.get_project(prj)
        return prj

    def get_user_config(self, project: _project.Project, user: _user.User):
        user_config = self.get_doc_by_filter(
            **{"user_id.$id": user.id, "project_id.$id": project.id, "active": True}
        )
        if not user_config:
            raise UserNotAssignedToProjectException(
                f"User `{user.username}` is not assigned to the project `{project.name}`."
            )
        return user_config

    def get_min_available_sshport(self, project: _project.Project) -> int:
        user_configs = (
            self._coll.find(
                filter={"project_id.$id": project.id},
                projection={"_id": 0, "ssh_port": 1},
            )
            .sort({"ssh_port": -1})
            .limit(1)
        )
        res = [uc["ssh_port"] for uc in user_configs]
        if res:
            return res[0] + 1
        return project.starting_port_bind

    def get_doc_by_id(self, _id: ObjectId) -> UserConfig | None:
        res = self._coll.find_one({"_id": _id})
        return UserConfig(**res) if res else None

    def get_doc_by_id_raw(self, _id: ObjectId):
        return self._coll.find_one({"_id": _id})

    def get_doc_by_filter(self, **kw) -> UserConfig | None:
        res = self._coll.find_one(filter=kw)
        return UserConfig(**res) if res else None

    def get_docs(self, **filter) -> list[UserConfig]:
        res = self._coll.find(filter=filter)
        return [UserConfig(**data) for data in res]

    def create_and_insert_doc(self, **kw) -> UserConfig:
        doc = UserConfig(_id=ObjectId(), **kw)
        self._coll.insert_one(asdict(doc))
        return doc

    # ASSIGN USER TO PROJECTS

    def assign_user_to_project(
        self,
        username: str,
        project_name: str,
        ssh_port: int = -1,
        forwarded_port: int = -1,
    ) -> UserConfig:
        user, project = self._get_user_and_project(username, project_name)
        users = self._prj_mgr.get_active_users_for_project_raw(project)
        user_config = self.get_doc_by_filter(
            **{"user_id.$id": user.id, "project_id.$id": project.id, "active": True}
        )

        if user_config:
            return user_config

        if len(users) >= project.max_nof_users:
            raise MaxUserCountReachedException(
                f"Project `{project.name}` has already reached the maximum number of users."
            )

        if ssh_port < 0:
            ssh_port = self.get_min_available_sshport(project)

        if forwarded_port < 0:
            forwarded_port = ssh_port

        collision_test = [
            i
            for i in self._coll.aggregate(
                [
                    {
                        "$match": {
                            "$and": [
                                {"active": True},
                                {
                                    "$or": [
                                        {"forwarded_port": forwarded_port},
                                        {"ssh_port": ssh_port},
                                    ]
                                },
                            ]
                        }
                    }
                ]
            )
        ]
        if collision_test:
            raise PortUsageCollisionException(
                f"Either forwarded port `{forwarded_port}` or system port `{ssh_port}`"
                "is already in use by another user in the project."
            )

        # create volume dir
        mount_dir = (
            Path(project.config_root_dir) / project.volume_mount_dirname / user.username
        )
        os.makedirs(mount_dir)
        os.chmod(mount_dir, 0o777)

        user_config = UserConfig(
            _id=ObjectId(),
            user_id=DBRef("user", user.id),
            project_id=DBRef("project", project.id),
            ssh_port=ssh_port,
            forwarded_port=forwarded_port,
        )

        self.insert_doc(user_config)
        return user_config

    def assign_multiple_users_to_project(
        self, lof_usernames: list[str], project_name: str
    ):
        # check project existence
        project = self._prj_mgr.get_doc_by_filter(name=project_name)
        if not project:
            raise ProjectNotExistsException(f"Project `{project_name}` does not exist.")

        nof_existing_users = len(
            self._prj_mgr.get_active_users_for_project_raw(project)
        )
        nof_new_users = len(lof_usernames)
        if nof_existing_users + nof_new_users > project.max_nof_users:
            raise MaxUserCountReachedException(
                f"Project `{project.name}` has already reached the maximum number of users."
            )

        min_sshport = self.get_min_available_sshport(project)
        if min_sshport + nof_new_users - 1 > 65_535:
            raise SSHPortOutOfRangeException("Not enough available ports.")

        users = self._user_mgr.get_docs(username={"$in": lof_usernames}, active=True)
        mount_dir = Path(project.config_root_dir) / project.volume_mount_dirname
        user_configs = []
        # TODO: collision_test
        for i, user in enumerate(users):
            os.makedirs(mount_dir / user.username)
            os.chmod(mount_dir / user.username, 777)
            user_configs.append(
                UserConfig(
                    _id=ObjectId(),
                    user_id=DBRef("user", user.id),
                    project_id=DBRef("project", project.id),
                    ssh_port=min_sshport + i,
                    forwarded_port=min_sshport + i,
                )
            )

        self._coll.insert_many([asdict(uc) for uc in user_configs])
        return user_configs

    # GET USER INFO

    def get_user_info(self, user: _user.User) -> list[dict[str, Any]]:
        pipeline = [
            {"$match": {"user_id.$id": user.id, "active": True}},
            {
                "$lookup": {
                    "from": "project",
                    "localField": "project_id.$id",
                    "foreignField": "_id",
                    "as": "project",
                }
            },
            {"$unwind": "$project"},
            {
                "$project": {
                    "_id": 0,
                    "project.name": 1,
                    "project.config_root_dir": 1,
                    "project.active": 1,
                }
            },
        ]
        return [i["project"] for i in self._coll.aggregate(pipeline)]

    # UNASSIGN USERS FROM PROJECTS

    def unassign_user_from_project(self, username: str, project_name: str):
        user, project = self._get_user_and_project(username, project_name)

        user_config = self.get_doc_by_filter(
            **{
                "user_id.$id": user.id,
                "project_id.$id": project.id,
                "active": True,
            }
        )

        if not user_config:
            raise UserNotAssignedToProjectException(
                f"User `{username}` is not assigned to the project `{project_name}`"
            )

        # create volume dir
        mount_dir = (
            Path(project.config_root_dir) / project.volume_mount_dirname / user.username
        )
        if mount_dir.exists() and mount_dir.is_dir() and len(str(mount_dir)) > 0:
            shutil.rmtree(mount_dir)

        podman_rm_networks(f"{project.name}_{user.username}_")

        user_config.active = False
        self.update_doc(user_config)

    def unassign_multiple_users_from_project(
        self, lof_usernames: list[str], project_name: str
    ):
        # check project existence
        project = self._get_project(project_name)
        user_configs = [
            i
            for i in self._coll.aggregate(
                self._multiple_users_pipeline(project, lof_usernames)
            )
        ]
        if not user_configs:
            return

        # remove mount dirs
        for uc in user_configs:
            mount_dir = (
                Path(project.config_root_dir)
                / project.volume_mount_dirname
                / uc.get("username")
            )
            if mount_dir.exists() and mount_dir.is_dir():
                shutil.rmtree(mount_dir)

        lof_prefix_name = list(
            map(lambda uc: f"{project.name}_{uc['username']}_", user_configs)
        )
        lof_network_names = podman_get_networks(lof_prefix_name)
        if lof_network_names:
            cmd = ["podman", "network", "rm"] + lof_network_names
            subprocess.run(cmd, stdout=sys.stdout, stderr=sys.stderr)

        uc_ids = [uc["_id"] for uc in user_configs]
        self._coll.update_many({"_id": {"$in": uc_ids}}, {"$set": {"active": False}})

    def unassign_all_from_project(self, project_or_name: str | _project.Project):
        """Unfollow all users from the project."""

        project = self._get_project(project_or_name)
        user_configs = [
            i for i in self._coll.aggregate(self._all_users_pipeline(project))
        ]
        if not user_configs:
            return

        # remove mount dirs
        for uc in user_configs:
            mount_dir = (
                Path(project.config_root_dir)
                / project.volume_mount_dirname
                / uc.get("username")
            )
            if mount_dir.exists() and mount_dir.is_dir():
                shutil.rmtree(mount_dir)

        lof_prefix_name = list(
            map(lambda uc: f"{project.name}_{uc['username']}_", user_configs)
        )
        lof_network_names = podman_get_networks(lof_prefix_name)
        if lof_network_names:
            cmd = ["podman", "network", "rm"] + lof_network_names
            subprocess.run(cmd, stdout=sys.stdout, stderr=sys.stderr)

        uc_ids = [uc["_id"] for uc in user_configs]
        self._coll.update_many({"_id": {"$in": uc_ids}}, {"$set": {"active": False}})

    def unassign_user_from_all_projects(self, user_or_username: str | _user.User):
        """Unassign the user from all the projects they are connected to."""
        user = self._get_user(user_or_username)
        pipeline = [
            {"$match": {"user_id.$id": user.id, "active": True}},
            {
                "$lookup": {
                    "from": "project",
                    "localField": "project_id.$id",
                    "foreignField": "_id",
                    "as": "project",
                    "pipeline": [{"$match": {"active": True}}],
                }
            },
            {"$unwind": "$project"},
        ]
        agg = self._coll.aggregate(pipeline)
        # get infos from the aggregation result
        lof_projects = [_project.Project(**i["project"]) for i in agg]
        if not lof_projects:
            return
        ids = [uc["_id"] for uc in agg]

        # remove mount dirs
        for project in lof_projects:
            mount_dir = (
                Path(project.config_root_dir)
                / project.volume_mount_dirname
                / user.username
            )
            if mount_dir.exists() and mount_dir.is_dir():
                shutil.rmtree(mount_dir)

        # create podman prefixes
        lof_prefix_name = list(
            map(lambda prj: f"{prj.name}_{user.username}_", lof_projects)
        )

        # delete networks
        lof_network_names = podman_get_networks(lof_prefix_name)
        if lof_network_names:
            cmd = ["podman", "network", "rm"] + lof_network_names
            subprocess.run(cmd, stdout=sys.stdout, stderr=sys.stderr)
        self._coll.update_many({"_id": {"$in": ids}}, {"$set": {"active": False}})

    # MANAGE MODULES

    def add_module(
        self,
        user_or_username: str | _user.User,
        project_or_name: str | _project.Project,
        module: Module,
    ):
        user = self._get_user(user_or_username)
        project = self._get_project(project_or_name)
        user_config = self.get_user_config(project, user)

        # add and compile
        if module.name in user_config.modules:
            raise ModuleExistsException(
                f"User `{user.username}` already has module `{module.name}`."
            )
        user_config.modules[module.name] = module
        self._compile_uc(user_config, project, user)
        self.update_doc(user_config)

    def remove_module(
        self,
        user_or_username: str | _user.User,
        project_or_name: str | _project.Project,
        module_name: str,
    ):
        user = self._get_user(user_or_username)
        project = self._get_project(project_or_name)
        user_config = self.get_user_config(project, user)
        if module_name in user_config.modules:
            user_config.modules.pop(module_name)

            # recompile
            self._compile_uc(user_config, project, user)
            self.update_doc(user_config)

    # RUNNING INSTANCES

    def start_user_instance(
        self,
        user_or_username: str | _user.User,
        project_or_name: str | _project.Project,
    ) -> subprocess.CompletedProcess:
        user = self._get_user(user_or_username)
        project = self._get_project(project_or_name)
        compose_file = Path(project.config_root_dir) / f"{user.username}_compose.yaml"

        # generate a compose file if not exist
        if not compose_file.is_file():
            user_config = self.get_user_config(project, user)
            self._compile_uc(user_config, project, user)

        cmd = f"podman-compose -f {str(compose_file)} up -d"
        proc = subprocess.run(cmd.split(), stdout=sys.stdout, stderr=sys.stderr)
        return proc

    def stop_user_instance(
        self,
        user_or_username: str | _user.User,
        project_or_name: str | _project.Project,
    ) -> subprocess.CompletedProcess:
        user = self._get_user(user_or_username)
        project = self._get_project(project_or_name)
        compose_file = Path(project.config_root_dir) / f"{user.username}_compose.yaml"
        cmd = f"podman-compose -f {str(compose_file)} down"
        proc = subprocess.run(cmd.split(), stdout=sys.stdout, stderr=sys.stderr)
        return proc

    def user_instance_is_running(
        self,
        user_or_username: str | _user.User,
        project_or_name: str | _project.Project,
    ) -> bool:
        user = self._get_user(user_or_username)
        project = self._get_project(project_or_name)

        compose_file = Path(project.config_root_dir) / f"{user.username}_compose.yaml"
        cmd = [
            "podman-compose",
            "-f",
            str(compose_file),
            "ps",
            "--format",
            '"{{ .Names }}"',
        ]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )
        data = proc.stdout.rsplit()
        return len(data) > 0

    def _compile_uc(
        self, user_config: UserConfig, project: _project.Project, user: _user.User
    ):
        compose_filepath = (
            Path(project.config_root_dir) / f"{user.username}_compose.yaml"
        )
        with open(str(compose_filepath), "w") as f:
            template = get_template(
                TEMPLATE_FILES["user_compose"], project.config_root_dir
            )
            f.write(
                template.render(project=project, user=user, user_config=user_config)
            )

    def compile_compose(
        self,
        user_or_username: str | _user.User,
        project_or_name: str | _project.Project,
    ):
        user = self._get_user(user_or_username)
        project = self._get_project(project_or_name)
        user_config = self.get_user_config(project, user)
        self._compile_uc(user_config, project, user)

    def restart_user_instance(
        self,
        user_or_username: str | _user.User,
        project_or_name: str | _project.Project,
    ):
        user = self._get_user(user_or_username)
        project = self._get_project(project_or_name)
        self.start_user_instance(user, project)
        self.stop_user_instance(user, project)

    def build_user_instance(
        self,
        user_or_username: str | _user.User,
        project_or_name: str | _project.Project,
    ):
        user = self._get_user(user_or_username)
        project = self._get_project(project_or_name)
        compose_file = Path(project.config_root_dir) / f"{user.username}_compose.yaml"
        cmd = f"podman-compose -f {compose_file} build"
        proc = subprocess.run(
            cmd.split(),
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
        return proc

    def stop_all_user_instances(self, project: _project.Project):
        """Stop all running user instances."""
        pipeline = [
            {"$match": {"project_id.$id": project.id, "active": True}},
            {
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
            {"$unwind": "$user"},
            {"$project": {"_id": 0, "user": 1}},
        ]
        lof_users = [_user.User(**i["user"]) for i in self._coll.aggregate(pipeline)]
        root_path = Path(project.config_root_dir)
        cmds = [
            f"podman-compose -f {str(root_path)}/{user.username}_compose.yaml down"
            for user in lof_users
        ]
        procs = [Popen(i.split()) for i in cmds]
        for p in procs:
            p.wait()
