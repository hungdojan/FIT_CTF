from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from subprocess import Popen
from typing import Any

from bson import DBRef, ObjectId
from pymongo.database import Database

import fit_ctf_db_models.project as _project
import fit_ctf_db_models.user as _user
from fit_ctf_backend.exceptions import (
    MaxUserCountReachedException,
    ModuleExistsException,
    PortUsageCollisionException,
    SSHPortOutOfRangeException,
    UserNotEnrolledToProjectException,
)
from fit_ctf_db_models.base import Base, BaseManager
from fit_ctf_db_models.compose_objects import Module
from fit_ctf_templates import TEMPLATE_FILES, get_template
from fit_ctf_utils.container_client.base_container_client import BaseContainerClient

log = logging.getLogger()


@dataclass(init=False)
class UserConfig(Base):
    """A class that represents a user configuration document.

    It serves as a connections between the project and the user. When a user enrolls to a
    project a new `user_config` document is created.

    :param user_id: A reference object that indicates a connection between a user and this
        document.
    :type user_id: DBRef
    :param project_id: A reference object that indicates a connection between a project
        and this document.
    :type project_id: DBRef
    :param ssh_port: An SSH port used to connect to login node.
    :type ssh_port: int
    :param forwarded_port: A forwarded port that user will connect to the outer server.
    :type forwarded_port: int
    :param modules: A collection of active modules that will start together with login
        node.
    :type modules: dict[str, Module]
    """

    user_id: DBRef
    project_id: DBRef
    ssh_port: int
    forwarded_port: int
    modules: dict[str, Module] = field(default_factory=dict)

    def __init__(self, **kwargs):
        """Constructor method."""
        # set default values
        self.modules = dict()
        self.active = True

        # ignore extra fields
        names = set([f.name for f in fields(self)])
        for k, v in kwargs.items():
            if k in names:
                setattr(self, k, v)


class UserConfigManager(BaseManager[UserConfig]):
    """A manager class that handles operations with `UserConfig` objects."""

    def __init__(self, db: Database, c_client: type[BaseContainerClient]):
        """Constructor method.

        :param db: A MongoDB database object.
        :type db: Database
        :param c_client: A container client class for calling container engine API.
        :type c_client: type[BaseContainerClient]
        """
        super().__init__(db, db["user_config"], c_client)

    @property
    def _prj_mgr(self) -> _project.ProjectManager:
        """Returns a project manager.

        :return: A project manager initialized in UserConfigManager.
        :rtype: _project.ProjectManager
        """
        return _project.ProjectManager(self._db, self.c_client)

    @property
    def _user_mgr(self) -> _user.UserManager:
        """Returns a user manager.

        :return: A user manager initialized in UserConfigManager.
        :rtype: _user.UserManager
        """
        return _user.UserManager(self._db, self.c_client)

    def _multiple_users_pipeline(
        self, project: _project.Project, lof_usernames: list[str]
    ) -> list:
        """A multiple user pipeline query template.

        :param project: Project object.
        :type project: _project.Project
        :param lof_usernames: A list of usernames to find.
        :type lof_usernames: list[str]
        :return: Generated query.
        :rtype: list
        """
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
        """An all users pipeline query template.

        :param project: Project object.
        :type project: _project.Project
        :return: Generated query.
        :rtype: list
        """
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
        """_summary_

        :param username: User username.
        :type username: str
        :param project_name: Project name.
        :type project_name: str
        :raises UserNotExistsException: User with the given username was not found.
        :raises ProjectNotExistException: Project data was not found in the database.
        :return: A found pair of `User` and `Project` objects.
        :rtype: tuple[_user.User, _project.Project]
        """
        user = self._user_mgr.get_user(username=username)
        project = self._prj_mgr.get_project(name=project_name)

        return user, project

    def _get_user(self, user_or_username: str | _user.User) -> _user.User:
        """Get a user from the username or user object.

        :param user_or_username: Username or a user object.
        :type user_or_username: str | _user.User
        :raises UserNotExistsException: User with the given username was not found.
        :return: User with the given name, or the same object that was passed into the
            function.
        :rtype: _user.User
        """
        user = user_or_username
        if not isinstance(user, _user.User):
            user = self._user_mgr.get_user(user)
        return user

    def _get_project(self, project_or_name: str | _project.Project) -> _project.Project:
        """Get a project from the project name or project object.

        :param project_or_name: Project name or a project object.
        :type project_or_name: str | _project.Project
        :raises ProjectNotExistException: Project data was not found in the database.
        :return: Found project or passed project object.
        :rtype: _project.Project
        """
        prj = project_or_name
        if not isinstance(prj, _project.Project):
            prj = self._prj_mgr.get_project(prj)
        return prj

    def user_is_enrolled_to_the_project(
        self, project: _project.Project, user: _user.User
    ) -> bool:
        """Check if user is enrolled to the given project.

        :param project: Project object.
        :type project: str
        :param user: User object.
        :type user: str
        :return: `True` if there is a user config document that links the project with
            the given user.
        :rtype: bool
        """
        user_config = self.get_doc_by_filter(
            **{"user_id.$id": user.id, "project_id.$id": project.id, "active": True}
        )
        return user_config is not None

    def get_user_config(
        self, project: _project.Project, user: _user.User
    ) -> UserConfig:
        """Get a user config document.

        :param project: Project object.
        :type project: _project.Project
        :param user: User object.
        :type user: _user.User
        :raises UserNotEnrolledToProjectException: Given user is not enrolled to the
            project.
        :return: The found user config document.
        :rtype: UserConfig
        """
        user_config = self.get_doc_by_filter(
            **{"user_id.$id": user.id, "project_id.$id": project.id, "active": True}
        )
        if not user_config:
            raise UserNotEnrolledToProjectException(
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

    def enroll_user_to_project(
        self,
        username: str,
        project_name: str,
        ssh_port: int = -1,
        forwarded_port: int = -1,
    ) -> UserConfig:
        """Enroll user to the project.

        :param username: User username.
        :type username: str
        :param project_name: Project name.
        :type project_name: str
        :param ssh_port: An SSH port of the login node. If set to `-1` the function will
            autogenerate a value. Defaults to -1.
        :type ssh_port: int, optional
        :param forwarded_port: A forwarded port for the user to connect to the outer
            server. If set to `-1` the function will autogenerate a value. Defaults to -1.
        :type forwarded_port: int, optional
        :raises UserNotExistsException: User with the given username was not found.
        :raises ProjectNotExistException: Project data was not found in the database.
        :raises MaxUserCountReachedException: Project has already reached the maximum
            number of enrolled users.
        :raises PortUsageCollisionException: The port is already in use.
        :return: A created `UserConfig` object.
        :rtype: UserConfig
        """
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

    def enroll_multiple_users_to_project(
        self, lof_usernames: list[str], project_name: str
    ) -> list[UserConfig]:
        """Enroll multiple users to the project.

        :param lof_usernames: A list of usernames.
        :type lof_usernames: list[str]
        :param project_name: Project name.
        :type project_name: str
        :raises ProjectNotExistException: Project with the given name does not exist.
        :raises MaxUserCountReachedException: Project has already reached the maximum
            number of enrolled users.
        :raises PortUsageCollisionException: The port is already in use.
        :return: A list of generated user configs.
        :rtype: list[UserConfig]
        """
        # check project existence
        project = self._prj_mgr.get_project(project_name)

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
        """Get user information.

        Retrieve all projects that the user is enrolled to. The final directory has a
        following format:
        {
            "name": <project_name>,
            "config_root_dir": <path_to_root_project_dir>,
            "active": <active_status>
        }

        :param user: A user object.
        :type user: _user.User
        :return: A list or retrieved projects.
        :rtype: list[dict[str, Any]]
        """
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

    # CANCEL USER ENROLLMENTS

    def cancel_user_enrollment(self, username: str, project_name: str):
        """Cancel user enrollment.

        :param username: User username.
        :type username: str
        :param project_name: Project name.
        :type project_name: str
        :raises UserNotExistsException: User with the given username was not found.
        :raises ProjectNotExistException: Project data was not found in the database.
        :raises UserNotEnrolledToProjectException: User is not enrolled to the given
        project.
        """
        user, project = self._get_user_and_project(username, project_name)

        user_config = self.get_doc_by_filter(
            **{
                "user_id.$id": user.id,
                "project_id.$id": project.id,
                "active": True,
            }
        )

        if not user_config:
            raise UserNotEnrolledToProjectException(
                f"User `{username}` is not enrolled to the project `{project_name}`"
            )

        # create volume dir
        mount_dir = (
            Path(project.config_root_dir) / project.volume_mount_dirname / user.username
        )
        if mount_dir.exists() and mount_dir.is_dir() and len(str(mount_dir)) > 0:
            shutil.rmtree(mount_dir)

        self.c_client.rm_networks(f"{project.name}_{user.username}_")

        user_config.active = False
        self.update_doc(user_config)

    def cancel_multiple_enrollments(self, lof_usernames: list[str], project_name: str):
        """Cancel multiple enrollment to a selected project.

        :param lof_usernames: A list of usernames.
        :type lof_usernames: list[str]
        :param project_name: Project name.
        :type project_name: str
        :raises ProjectNotExistException: Project data was not found in the database.
        """
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
        lof_network_names = self.c_client.get_networks(lof_prefix_name)
        if lof_network_names:
            cmd = ["podman", "network", "rm"] + lof_network_names
            subprocess.run(cmd, stdout=sys.stdout, stderr=sys.stderr)

        uc_ids = [uc["_id"] for uc in user_configs]
        self._coll.update_many({"_id": {"$in": uc_ids}}, {"$set": {"active": False}})

    def cancel_all_project_enrollments(self, project_or_name: str | _project.Project):
        """Remove all user enrollments for the given project.

        :param project_or_name: Project name or `Project` object.
        :type project_or_name: str | _project.Project
        :raises ProjectNotExistException: Project data was not found in the database.
        """

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
        lof_network_names = self.c_client.get_networks(lof_prefix_name)
        if lof_network_names:
            cmd = ["podman", "network", "rm"] + lof_network_names
            subprocess.run(cmd, stdout=sys.stdout, stderr=sys.stderr)

        uc_ids = [uc["_id"] for uc in user_configs]
        self._coll.update_many({"_id": {"$in": uc_ids}}, {"$set": {"active": False}})

    def cancel_user_enrollments_from_all_projects(
        self, user_or_username: str | _user.User
    ):
        """Remove user from all enrolled projects.

        :param user_or_username: User username or `User` object.
        :type user_or_username: str | _user.User
        :raises UserNotExistsException: User with the given username was not found.
        """
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
        lof_network_names = self.c_client.get_networks(lof_prefix_name)
        if lof_network_names:
            cmd = ["podman", "network", "rm"] + lof_network_names
            subprocess.run(cmd, stdout=sys.stdout, stderr=sys.stderr)
        self._coll.update_many({"_id": {"$in": ids}}, {"$set": {"active": False}})

    def clear_database(self):
        """Remove all canceled user enrollments."""
        self.remove_docs_by_filter(active=False)

    # MANAGE MODULES

    def add_module(
        self,
        user_or_username: str | _user.User,
        project_or_name: str | _project.Project,
        module: Module,
    ):
        """Add a new module to the login node.

        :param user_or_username: User username or `User` object.
        :type user_or_username: str | _user.User
        :param project_or_name: Project name or `Project` object.
        :type project_or_name: str | _project.Project
        :param module: Module object.
        :type module: Module
        :raises UserNotExistsException: User with the given username was not found.
        :raises ProjectNotExistException: Project data was not found in the database.
        :raises UserNotEnrolledToProjectException: Given user is not enrolled to the
            project.
        :raises ModuleExistsException: The module is already assigned to the given login
            node.
        """
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
        """Remove a module from the login node.

        :param user_or_username: User username or `User` object.
        :type user_or_username: str | _user.User
        :param project_or_name: Project name or `Project` object.
        :type project_or_name: str | _project.Project
        :param module_name: Module name.
        :type module: str
        :raises UserNotExistsException: User with the given username was not found.
        :raises ProjectNotExistException: Project data was not found in the database.
        :raises UserNotEnrolledToProjectException: Given user is not enrolled to the
            project.
        """
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
        """Start user login nodes.

        :param user_or_username: User username or `User` object.
        :type user_or_username: str | _user.User
        :param project_or_name: Project name or `Project` object.
        :type project_or_name: str | _project.Project
        :raises UserNotExistsException: User with the given username was not found.
        :raises ProjectNotExistException: Project data was not found in the database.
        :raises UserNotEnrolledToProjectException: Given user is not enrolled to the
            project.
        :return: A completed process data.
        :rtype: subprocess.CompletedProcess
        """
        user = self._get_user(user_or_username)
        project = self._get_project(project_or_name)
        if not self.user_is_enrolled_to_the_project(project, user):
            raise UserNotEnrolledToProjectException(
                f"User `{user.username}` is not enrolled to `{project.name}`."
            )
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
        """Stop user login nodes.

        :param user_or_username: User username or `User` object.
        :type user_or_username: str | _user.User
        :param project_or_name: Project name or `Project` object.
        :type project_or_name: str | _project.Project
        :raises UserNotExistsException: User with the given username was not found.
        :raises ProjectNotExistException: Project data was not found in the database.
        :raises UserNotEnrolledToProjectException: Given user is not enrolled to the
            project.
        :return: A completed process data.
        :rtype: subprocess.CompletedProcess
        """
        user = self._get_user(user_or_username)
        project = self._get_project(project_or_name)
        if not self.user_is_enrolled_to_the_project(project, user):
            raise UserNotEnrolledToProjectException(
                f"User `{user.username}` is not enrolled to `{project.name}`."
            )

        compose_file = Path(project.config_root_dir) / f"{user.username}_compose.yaml"
        cmd = f"podman-compose -f {str(compose_file)} down"
        proc = subprocess.run(cmd.split(), stdout=sys.stdout, stderr=sys.stderr)
        return proc

    def user_instance_is_running(
        self,
        user_or_username: str | _user.User,
        project_or_name: str | _project.Project,
    ) -> bool:
        """Check if user login nodes are running.

        :param user_or_username: User username or `User` object.
        :type user_or_username: str | _user.User
        :param project_or_name: Project name or `Project` object.
        :type project_or_name: str | _project.Project
        :raises UserNotExistsException: User with the given username was not found.
        :raises ProjectNotExistException: Project data was not found in the database.
        :raises UserNotEnrolledToProjectException: Given user is not enrolled to the
            project.
        :return: `True` if login nodes are up.
        :rtype: bool
        """
        user = self._get_user(user_or_username)
        project = self._get_project(project_or_name)
        if not self.user_is_enrolled_to_the_project(project, user):
            raise UserNotEnrolledToProjectException(
                f"User `{user.username}` is not enrolled to `{project.name}`."
            )

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
        """Use the given user config document to compile user compose file.

        :param user_config: A `user_config` object.
        :type user_config: UserConfig
        :param project: Project object.
        :type project: _project.Project
        :param user: User object.
        :type user: _user.User
        """
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
        """Compile user compose file.

        :param user_or_username: User username or `User` object.
        :type user_or_username: str | _user.User
        :param project_or_name: Project name or `Project` object.
        :type project_or_name: str | _project.Project
        :raises UserNotExistsException: User with the given username was not found.
        :raises ProjectNotExistException: Project data was not found in the database.
        :raises UserNotEnrolledToProjectException: Given user is not enrolled to the
            project.
        """
        user = self._get_user(user_or_username)
        project = self._get_project(project_or_name)
        user_config = self.get_user_config(project, user)
        self._compile_uc(user_config, project, user)

    def restart_user_instance(
        self,
        user_or_username: str | _user.User,
        project_or_name: str | _project.Project,
    ):
        """Compile user compose file.

        :param user_or_username: User username or `User` object.
        :type user_or_username: str | _user.User
        :param project_or_name: Project name or `Project` object.
        :type project_or_name: str | _project.Project
        :raises UserNotExistsException: User with the given username was not found.
        :raises ProjectNotExistException: Project data was not found in the database.
        :raises UserNotEnrolledToProjectException: Given user is not enrolled to the
            project.
        """
        user = self._get_user(user_or_username)
        project = self._get_project(project_or_name)
        if not self.user_is_enrolled_to_the_project(project, user):
            raise UserNotEnrolledToProjectException(
                f"User `{user.username}` is not enrolled to the project `{project.name}`."
            )
        self.start_user_instance(user, project)
        self.stop_user_instance(user, project)

    def build_user_instance(
        self,
        user_or_username: str | _user.User,
        project_or_name: str | _project.Project,
    ):
        """Build user login nodes using `podman-compose` command.

        :param user_or_username: User username or `User` object.
        :type user_or_username: str | _user.User
        :param project_or_name: Project name or `Project` object.
        :type project_or_name: str | _project.Project
        :raises UserNotExistsException: User with the given username was not found.
        :raises ProjectNotExistException: Project data was not found in the database.
        :raises UserNotEnrolledToProjectException: Given user is not enrolled to the
            project.
        """
        user = self._get_user(user_or_username)
        project = self._get_project(project_or_name)
        if not self.user_is_enrolled_to_the_project(project, user):
            raise UserNotEnrolledToProjectException(
                f"User `{user.username}` is not enrolled to the project `{project.name}`."
            )
        compose_file = Path(project.config_root_dir) / f"{user.username}_compose.yaml"
        cmd = f"podman-compose -f {compose_file} build"
        proc = subprocess.run(
            cmd.split(),
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
        return proc

    def stop_all_user_instances(self, project: _project.Project):
        """Stop all login nodes.

        :param project: A project object.
        :type project: _project.Project
        """
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
