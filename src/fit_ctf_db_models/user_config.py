from __future__ import annotations

import logging
import os
import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path
from pprint import pprint
from typing import Any

from bson import DBRef, ObjectId
from pymongo.database import Database

import fit_ctf_db_models.project as _project
import fit_ctf_db_models.user as _user
from fit_ctf_backend import (
    ProjectNotExistsException,
    SSHPortOutOfRangeException,
    UserNotAssignedToProjectException,
    UserNotExistsException,
)
from fit_ctf_backend.exceptions import (
    MaxUserCountReachedException,
    PortUsageCollisionException,
)
from fit_ctf_db_models.base import Base, BaseManager
from fit_ctf_db_models.service import Service
from fit_ctf_templates import TEMPLATE_FILES, get_template

log = logging.getLogger()


@dataclass
class UserConfig(Base):
    _id: ObjectId
    user_id: DBRef
    project_id: DBRef
    ssh_port: int
    forwarded_port: int = -1
    services: list[Service] = field(default_factory=list)
    active: bool = True

    def get_template(self):
        template = get_template(TEMPLATE_FILES["shadow"])
        # TODO: create tempfile
        raise NotImplemented()


class UserConfigManager(BaseManager[UserConfig]):
    def __init__(self, db: Database):
        super().__init__(db, db["user_config"])

    @property
    def _prj_mgr(self):
        return _project.ProjectManager(self._db)

    @property
    def _user_mgr(self):
        return _user.UserManager(self._db)

    def _get_user_and_project(
        self, username: str, project_name: str
    ) -> tuple[_user.User, _project.Project]:
        user = self._user_mgr.get_doc_by_filter(username=username)
        if not user:
            raise UserNotExistsException(f"User `{username}` does not exist.")

        project = self._prj_mgr.get_doc_by_filter(name=project_name)
        if not project:
            raise ProjectNotExistsException(f"Project `{project_name}` does not exist.")

        return user, project

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

    def add_user_to_project(
        self,
        username: str,
        project_name: str,
        ssh_port: int = -1,
        forwarded_port: int = -1,
    ) -> UserConfig:
        user, project = self._get_user_and_project(username, project_name)
        users = self._prj_mgr.get_active_users_for_project(project)
        user_config = self.get_doc_by_filter(
            **{
                "user_id.$id": user.id,
                "project_id.$id": project.id,
            }
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
                            "$or": [
                                {"forwarded_port": forwarded_port},
                                {"ssh_port": ssh_port},
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

        user_config = UserConfig(
            _id=ObjectId(),
            user_id=DBRef("user", user.id),
            project_id=DBRef("project", project.id),
            ssh_port=ssh_port,
            forwarded_port=forwarded_port,
        )

        self.insert_doc(user_config)
        return user_config

    def add_multiple_users_to_project(
        self, lof_usernames: list[str], project_name: str
    ):
        # check project existence
        project = self._prj_mgr.get_doc_by_filter(name=project_name)
        if not project:
            raise ProjectNotExistsException(f"Project `{project_name}` does not exist.")

        nof_existing_users = len(self._prj_mgr.get_active_users_for_project(project))
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

    def remove_user_from_project(self, username: str, project_name: str):
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

        user_config.active = False
        self.update_doc(user_config)

    def remove_multiple_users_from_project(
        self, lof_usernames: list[str], project_name: str
    ):
        # check project existence
        project = self._prj_mgr.get_doc_by_filter(name=project_name)
        if not project:
            raise ProjectNotExistsException(f"Project `{project_name}` does not exist.")

        pipeline = [
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
                                "user.username": {"$in": lof_usernames},
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
                    "shadow_path": "$user.shadow_path",
                }
            },
        ]
        user_configs = [i for i in self._coll.aggregate(pipeline)]

        # remove mount dirs
        for uc in user_configs:
            mount_dir = (
                Path(project.config_root_dir)
                / project.volume_mount_dirname
                / uc.get("username")
            )
            if mount_dir.exists() and mount_dir.is_dir():
                # shutil.rmtree(mount_dir)
                pass

            shadow_path = Path(uc["shadow_path"])
            if shadow_path.exists():
                shadow_path.unlink()
        # return self.remove_docs_by_id([uc["_id"] for uc in user_configs])
        return 0

    def unassign_users(self, project_or_name: str | _project.Project):
        """Unfollow all users from the project."""

        prj = project_or_name
        if not isinstance(prj, _project.Project):
            prj = self._prj_mgr.get_doc_by_filter(name=project_or_name)
            if not prj:
                raise ProjectNotExistsException(
                    f"Project `{project_or_name}` does not exist."
                )

        ids = [
            uc.id for uc in self.get_docs(**{"project_id.$id": prj.id, "active": True})
        ]
        self._coll.update_many({"_id": {"$in": ids}}, {"$set": {"active": False}})

    def unassign_user_from_projects(self, user_or_username: str | _user.User):
        """Unassign the user from all the projects they are connected to."""
        user = user_or_username
        if not isinstance(user, _user.User):
            user = self._user_mgr.get_doc_by_filter(username=user_or_username)
            if not user:
                raise UserNotExistsException(
                    f"User `{user_or_username}` does not exist."
                )
        ids = [
            uc.id for uc in self.get_docs(**{"user_id.$id": user.id, "active": True})
        ]
        self._coll.update_many({"_id": {"$in": ids}}, {"$set": {"active": False}})
