from __future__ import annotations

import os
import subprocess

import pymongo
from pymongo.database import Database

from fit_ctf_backend.exceptions import ProjectNotExistException
from fit_ctf_db_models import Project, ProjectManager, UserConfigManager, UserManager
from fit_ctf_utils import get_c_client_by_name


class CTFManager:
    def __init__(self, host: str, db_name: str):
        """Constructor method

        :param host: A URL to connect to the database.
        :type host: str
        :param db_name: Name of the database that contain CTF data.
        :type db_name: str
        """
        self._client = pymongo.MongoClient(
            host, serverSelectionTimeoutMS=int(os.getenv("DB_CONNECTION_TIMEOUT", "30"))
        )
        # test connection
        self._client.server_info()

        self._ctf_db: Database = self._client[db_name]
        c_client = get_c_client_by_name(os.getenv("CONTAINER_CLIENT", ""))
        self._managers = {
            "project": ProjectManager(self._ctf_db, c_client),
            "user": UserManager(self._ctf_db, c_client),
            "user_config": UserConfigManager(self._ctf_db, c_client),
        }

    @property
    def prj_mgr(self) -> ProjectManager:
        """Returns a project manager.

        :return: A project manager initialized in CTFManager.
        :rtype: ProjectManager
        """
        return self._managers["project"]

    @property
    def user_mgr(self) -> UserManager:
        """Returns a user manager.

        :return: A user manager initialized in CTFManager.
        :rtype: UserManager
        """
        return self._managers["user"]

    @property
    def user_config_mgr(self) -> UserConfigManager:
        """Returns a user config manager.

        :return: A user config manager initialized in CTFManager.
        :rtype: UserConfigManager
        """
        return self._managers["user_config"]

    def init_project(
        self,
        name: str,
        dest_dir: str,
        max_nof_users: int,
        starting_port_bind: int,
        volume_mount_dirname: str,
        dir_name: str | None,
        description: str,
        compose_file: str,
    ) -> Project:
        """A wrapper function that creates and initializes a project.

        :param name: Project's name.
        :type name: str
        :param dest_dir: A destination directory where project data will be stored.
        :type name: str
        :param max_nof_users: Number of users that can enroll the project.
        :type max_nof_users: int
        :param starting_port_bind: A ssh port of the first enrolled user. When
            -1 is set the function will automatically find and assign available
            port.
        :type starting_port_bind: int
        :param volume_mount_dirname: A destination directory that will contain
            user mount directories/images. If the path does not exist, it will be
            create inside `dest_dir`.
        :type volume_mount_dirname: str
        :param dir_name: A project directory name. If not set function will
            auto-generate one
        :type dir_name: str | None
        :param description: A project description.
        :type description: str
        :param compose_file: Name of the server nodes' compose file.
        :type compose_file: str

        :raises ProjectExistsException: Project with the given name already exist.
        :raises DirNotExistsException: A path to `dest_dir` does not exist.
        :raises DirNotExistsException: A `dest_dir` directory is not empty.

        :return: A created project object.
        :rtype: class `Project`
        """

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

    def start_project(self, name: str) -> int:
        """Starts all server nodes in a project.

        :param name: Project name.
        :type name: str
        :return: Returns a process return code. Returns `-1` when project not found.
        :rtype: int
        """
        try:
            project = self.prj_mgr.get_project(name)
        except ProjectNotExistException:
            return -1
        proc = self.prj_mgr.start_project(project)
        return proc.returncode

    def stop_project(self, name: str) -> int:
        """Stop all server nodes in the project.

        :param name: Project name.
        :type name: str
        :return: Returns a process return code. Returns `-1` when project not found.
        :rtype: int
        """
        try:
            project = self.prj_mgr.get_project(name)
        except ProjectNotExistException:
            return -1

        self.user_config_mgr.stop_all_user_instances(project)
        proc = self.prj_mgr.stop_project(project)
        return proc.returncode

    def project_is_running(self, name: str) -> bool:
        """Check if project is running.

        :param name: Project name.
        :type name: str
        :return: `True` if server nodes are running.
        :rtype: bool
        """
        try:
            project = self.prj_mgr.get_project(name)
        except ProjectNotExistException:
            return False
        return self.prj_mgr.is_running(project)

    def project_status(self, name: str) -> subprocess.CompletedProcess:
        """Print a result of `podman ps` command.

        :param name: Project name.
        :type name: str
        :return: A completed process object.
        :raises ProjectNotExistException: Project with the given name was not found.
        :rtype: subprocess.CompletedProcess
        """
        project = self.prj_mgr.get_project(name)
        return self.prj_mgr.c_client.ps(project.name)

    def start_user_instance(
        self, username: str, project_name: str
    ) -> subprocess.CompletedProcess:
        """Start a user login node.

        :param username: User username.
        :type username: str
        :param project_name: Project name.
        :type project_name: str
        :return: A completed process object.
        :rtype: subprocess.CompletedProcess
        """
        return self.user_config_mgr.start_user_instance(username, project_name)

    def stop_user_instance(
        self, username: str, project_name: str
    ) -> subprocess.CompletedProcess:
        """Stop a user login node.

        :param username: User username.
        :type username: str
        :param project_name: Project name.
        :type project_name: str
        :return: A completed process object.
        :rtype: subprocess.CompletedProcess
        """
        return self.user_config_mgr.stop_user_instance(username, project_name)

    def user_instance_is_running(self, username: str, project_name: str) -> bool:
        """Check if user login node is running.

        :param username: User username.
        :type username: str
        :param project_name: Project name.
        :type project_name: str
        :return: `True` if the login node is running.
        :rtype: bool
        """
        return self.user_config_mgr.user_instance_is_running(username, project_name)

    def delete_project(self, name: str) -> None:
        """Delete a project.

        :param name: Project name.
        :type name: str
        :raises ProjectNotExistException: Project was not found.
        """
        self.prj_mgr.delete_project(name)

    def enroll_users_to_project(self, users: str | list[str], project_name: str):
        """Enroll users to the project

        :param users: A username or a list of usernames.
        :type users: str | list[str]
        :raises ProjectNotExistException: Project was not found.
        :param project_name: Project name.
        :type project_name: str
        """
        if isinstance(users, str):
            self.user_config_mgr.enroll_user_to_project(users, project_name)
        else:
            self.user_config_mgr.enroll_multiple_users_to_project(users, project_name)

    def cancel_user_enrollments(self, users: str | list[str], project_name: str):
        """Cancel user enrollments to the project.

        :param users: A username or a list of usernames.
        :type users: str | list[str]
        :raises ProjectNotExistException: Project was not found.
        :param project_name: Project name.
        :type project_name: str
        """
        if isinstance(users, str):
            self.user_config_mgr.cancel_user_enrollment(users, project_name)
        else:
            self.user_config_mgr.cancel_multiple_enrollments(users, project_name)

    def health_check(self, name: str):
        """Run a health check.

        :param name: Project name.
        :type name: str
        :raises NotImplemented: This function was not implemented yet.
        """
        raise NotImplemented()

    def get_project_info(self, name: str) -> Project | None:
        """Get project information.

        :param name: Project name.
        :type name: str
        :return: Found project object or `None`.
        :rtype: Project | None
        """
        return self.prj_mgr.get_doc_by_filter(name=name)
