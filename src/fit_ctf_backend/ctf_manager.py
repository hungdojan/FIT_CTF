from __future__ import annotations

import subprocess

from pymongo import MongoClient
from pymongo.database import Database

from fit_ctf_backend.exceptions import CTFException, ProjectNotExistsException
from fit_ctf_db_models import Project, ProjectManager, UserConfigManager, UserManager


class CTFManager:
    def __init__(self, host: str, db_name: str):
        self._client = MongoClient(host)
        self._ctf_db: Database = self._client[db_name]
        self._managers = {
            "project": ProjectManager(self._ctf_db),
            "user": UserManager(self._ctf_db),
            "user_config": UserConfigManager(self._ctf_db),
        }

    @property
    def prj_mgr(self) -> ProjectManager:
        return self._managers["project"]

    @property
    def user_mgr(self) -> UserManager:
        return self._managers["user"]

    @property
    def user_config_mgr(self) -> UserConfigManager:
        return self._managers["user_config"]

    def init_project(
        self,
        name: str,
        dest_dir: str,
        max_nof_users: int,
        starting_port_bind: int,
        volume_mount_dirname: str,
        dir_name: str,
        description: str,
        compose_file: str,
    ) -> Project:
        """Create a project template."""
        # check if project already exists
        return self.prj_mgr.init_project(
            name,
            dest_dir,
            max_nof_users,
            starting_port_bind,
            volume_mount_dirname,
            dir_name,
            description,
            compose_file,
        )

    def start_project(self, name: str) -> bool:
        project = self.prj_mgr.get_doc_by_filter(name=name)
        if not project:
            raise ProjectNotExistsException(f"Project `{name}` does not exist.")
        proc = project.start()
        return proc.returncode != 0

    def stop_project(self, name: str) -> bool:
        project = self.prj_mgr.get_doc_by_filter(name=name)
        if not project:
            raise ProjectNotExistsException(f"Project `{name}` does not exist.")

        self.user_config_mgr.stop_all_user_instances(project)
        proc = project.stop()
        return proc.returncode != 0

    def project_is_running(self, name: str) -> bool:
        project = self.prj_mgr.get_doc_by_filter(name=name)
        if not project:
            raise ProjectNotExistsException(f"Project `{name}` does not exist.")
        return project.is_running()

    def start_user_instance(
        self, username: str, project_name: str
    ) -> subprocess.CompletedProcess:
        return self.user_config_mgr.start_user_instance(username, project_name)

    def stop_user_instance(
        self, username: str, project_name: str
    ) -> subprocess.CompletedProcess:
        return self.user_config_mgr.stop_user_instance(username, project_name)

    def user_instance_is_running(self, username: str, project_name: str) -> bool:
        return self.user_config_mgr.user_instance_is_running(username, project_name)

    def delete_project(self, name: str):
        """Delete a project."""
        try:
            return self.prj_mgr.delete_project(name)
        except CTFException as e:
            print(e)

    def assign_users_to_project(self, users: str | list[str], project_name: str):
        if isinstance(users, str):
            self.user_config_mgr.assign_user_to_project(users, project_name)
        else:
            self.user_config_mgr.assign_multiple_users_to_project(users, project_name)

    def unassign_user_from_project(self, users: str | list[str], project_name: str):
        if isinstance(users, str):
            self.user_config_mgr.unassign_user_from_project(users, project_name)
        else:
            self.user_config_mgr.unassign_multiple_users_from_project(
                users, project_name
            )

    def get_running_projects(self):
        raise NotImplemented()

    def export_project_configs(self, name: str):
        # TODO: figure out what to export
        raise NotImplemented()

    def get_project_info(self, name: str) -> Project | None:
        return self.prj_mgr.get_doc_by_filter(name=name)
