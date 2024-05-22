from __future__ import annotations

import logging
import os
import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path
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

    def _get_user_and_project(
        self, username: str, project_name: str
    ) -> tuple[_user.User, _project.Project]:
        user_mgr = _user.UserManager(self._db)
        prj_mgr = _project.ProjectManager(self._db)
        user = user_mgr.get_doc_by_filter(username=username)
        if not user:
            raise UserNotExistsException(f"User `{username}` does not exist.")

        project = prj_mgr.get_doc_by_filter(name=project_name)
        if not project:
            raise ProjectNotExistsException(f"Project `{project_name}` does not exist.")

        return user, project

    def get_min_available_sshport(self, project_name: str) -> int:
        prj_mgr = _project.ProjectManager(self._db)
        prj = prj_mgr.get_doc_by_filter(name=project_name)
        if not prj:
            raise ProjectNotExistsException(f"Project `{project_name}` does not exist.")

        user_configs = self.get_docs_raw(
            filter={"project_id.$id": prj.id}, projection={"_id": 0, "ssh_port": 1}
        )
        self._coll.find(
            filter={"project_id.$id": prj.id}, projection={"_id": 0, "ssh_port": 1}
        ).sort({"ssh_port": -1}).limit(1)
        res = [uc["ssh_port"] for uc in user_configs]
        if res:
            return res[0] + 1
        return 50000

    def get_doc_by_id(self, _id: ObjectId) -> UserConfig | None:
        res = self._coll.find_one({"_id": _id})
        return UserConfig(**res) if res else None

    def get_doc_by_id_raw(self, _id: ObjectId):
        return self._coll.find_one({"_id": _id})

    def get_doc_by_filter(self, **kw) -> UserConfig | None:
        res = self._coll.find_one(filter=kw)
        return UserConfig(**res) if res else None

    def get_docs(self, filter: dict[str, Any]) -> list[UserConfig]:
        res = self._coll.find(filter=filter)
        return [UserConfig(**data) for data in res]

    def create_and_insert_doc(self, **kw) -> UserConfig:
        doc = UserConfig(_id=ObjectId(), **kw)
        self._coll.insert_one(asdict(doc))
        return doc

    def add_user_to_project(
        self, username: str, project_name: str, ssh_port: int = -1
    ) -> UserConfig:
        user, project = self._get_user_and_project(username, project_name)

        # create volume dir
        mount_dir = Path(project.volume_mount_root_dir) / user.username
        os.makedirs(str(mount_dir))

        user_config = self.get_doc_by_filter(
            **{
                "user_id.$id": user.id,
                "project_id.$id": project.id,
            }
        )

        if user_config:
            return user_config

        if ssh_port < 0:
            ssh_port = self.get_min_available_sshport(project_name)

        user_config = UserConfig(
            _id=ObjectId(),
            user_id=DBRef("user", user.id),
            project_id=DBRef("project", project.id),
            ssh_port=ssh_port,
        )

        self.insert_doc(user_config)
        return user_config

    def add_multiple_users_to_project(
        self, lof_usernames: list[str], project_name: str
    ):
        user_mgr = _user.UserManager(self._db)
        prj_mgr = _project.ProjectManager(self._db)

        # check project existence
        project = prj_mgr.get_doc_by_filter(name=project_name)
        if not project:
            raise ProjectNotExistsException(f"Project `{project_name}` does not exist.")

        min_sshport = self.get_min_available_sshport(project_name)
        if min_sshport + len(lof_usernames) - 1 > 65_535:
            raise SSHPortOutOfRangeException("Not enough available ports.")

        users = user_mgr.get_docs(filter={"username": {"$in": lof_usernames}})
        user_configs = []
        for i, user in enumerate(users):
            os.makedirs(f"{project.volume_mount_root_dir}{user.username}")
            user_configs.append(
                UserConfig(
                    _id=ObjectId(),
                    user_id=DBRef("user", user.id),
                    project_id=DBRef("project", project.id),
                    ssh_port=min_sshport + i,
                )
            )

        self._coll.insert_many([asdict(uc) for uc in user_configs])
        return user_configs

    def remove_user_from_project(self, username: str, project_name: str) -> bool:
        user, project = self._get_user_and_project(username, project_name)

        user_config = self.get_doc_by_filter(
            **{
                "user_id.$id": user.id,
                "project_id.$id": project.id,
            }
        )

        if not user_config:
            raise UserNotAssignedToProjectException(
                "User `{username}` is not assigned to the project `{project_name}`"
            )

        # create volume dir
        mount_dir = Path(project.volume_mount_root_dir) / user.username
        if mount_dir.exists() and mount_dir.is_dir():
            # shutil.rmtree(mount_dir)
            pass
        print(user_config, mount_dir)

        # return self.remove_doc_by_id(user_config.id)
        return False

    def remove_multiple_users_from_project(
        self, lof_usernames: list[str], project_name: str
    ) -> int:
        prj_mgr = _project.ProjectManager(self._db)

        # check project existence
        project = prj_mgr.get_doc_by_filter(name=project_name)
        if not project:
            raise ProjectNotExistsException(f"Project `{project_name}` does not exist.")

        pipeline = [
            {
                # get configs for a given project
                "$match": {"project_id.$id": project.id}
            },
            {
                # get user info
                "$lookup": {
                    "from": "user",
                    "localField": "user_id.$id",
                    "foreignField": "_id",
                    "as": "user",
                }
            },
            {
                # pop first element from the array
                "$unwind": "$user"
            },
            {
                # search for users in the given list of username
                "$match": {"user.username": {"$in": lof_usernames}}
            },
            {
                # transform to the final internet format
                "$project": {
                    "username": "$user.username",
                }
            },
        ]
        user_configs = [i for i in self._coll.aggregate(pipeline)]

        # remove mount dirs
        for uc in user_configs:
            mount_dir = Path(project.volume_mount_root_dir) / uc.get("username")
            if mount_dir.exists() and mount_dir.is_dir():
                # shutil.rmtree(mount_dir)
                pass
            print(uc["_id"], mount_dir)
        # return self.remove_docs_by_id([uc["_id"] for uc in user_configs])
        return 0
