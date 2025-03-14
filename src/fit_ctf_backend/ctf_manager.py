import os
from pathlib import Path
from shutil import copytree
from typing import Literal

import pymongo
from pymongo.database import Database

from fit_ctf_db_models import (
    ProjectManager,
    UserEnrollmentManager,
    UserManager,
)
from fit_ctf_utils import get_c_client_by_name
from fit_ctf_utils import log_print as log
from fit_ctf_utils.types import PathDict


class CTFManager:
    def __init__(self, host: str, db_name: str, paths: PathDict):
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
        self._init_paths(paths)

        c_client = get_c_client_by_name(os.getenv("CONTAINER_CLIENT", ""))
        self._managers = {
            "project": ProjectManager(self._ctf_db, c_client, paths),
            "user": UserManager(self._ctf_db, c_client, paths),
            "user_enrollment": UserEnrollmentManager(self._ctf_db, c_client, paths),
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
    def user_enrollment_mgr(self) -> UserEnrollmentManager:
        """Returns a user enrollment manager.

        :return: A user enrollment manager initialized in CTFManager.
        :rtype: UserEnrollmentManager
        """
        return self._managers["user_enrollment"]

    def _init_paths(self, paths: PathDict):
        """Initialize path directories for the current session."""
        self._paths = paths
        if not self._paths["projects"].exists():
            log.info(
                f"Creating central project directory `{str(self._paths['projects'].resolve())}`..."
            )
            self._paths["projects"].mkdir(parents=True, exist_ok=True)
        if not self._paths["users"].exists():
            log.info(
                f"Creating central user directory `{str(self._paths['users'].resolve())}`..."
            )
            self._paths["users"].mkdir(parents=True, exist_ok=True)
        if not self._paths["modules"].exists():
            log.info(
                f"Creating central module directory `{str(self._paths['modules'].resolve())}`..."
            )
            self._paths["modules"].mkdir(parents=True, exist_ok=True)

        if not (self._paths["modules"] / "base").exists():
            self.init_tool()

    def init_tool(self, base_image_os: Literal["rhel", "ubuntu"] = "rhel"):
        """Initialize base images."""
        if not (self._paths["modules"] / "base").exists():
            dst_path = self._paths["modules"] / "base"
            root_dir = (
                Path(os.path.dirname(os.path.realpath(__file__))).parent.parent
                / "config"
                / "base_images"
            )

            if base_image_os not in {"rhel", "ubuntu"}:
                raise ValueError(
                    "The only supported base image OS are `rhel` or `ubuntu`."
                )
            src_path = root_dir / f"base_{base_image_os}"
            copytree(str(src_path.resolve()), str(dst_path.resolve()))

    def export_data(self):
        raise NotImplementedError()

    # FIX: completely rewrite the function
    # the function should generate a YAML file that the user will be able to
    # import on a different machine
    # def export_project(self, project_or_name: str | Project, output_file: str):
    #     """Export project configuration files.

    #     Generate a ZIP archive.

    #     :param project_name: Project name or the instance.
    #     :type project_name: str | Project
    #     :param output_file: Output filename.
    #     :type output_file: str
    #     :raises ProjectNotExistException: Project was not found.
    #     """
    #     # TODO: implement this
    #     raise NotImplementedError()
    # prj = self.get_project(project_or_name)
    # with zipfile.ZipFile(output_file, "w", zipfile.ZIP_DEFLATED) as zf:
    #     # add a file containing list of enrolled users
    #     zf.writestr(
    #         "enrolled_users.json",
    #         json.dumps(self.get_active_users_for_project_raw(prj)),
    #     )

    #     # this code snippet originates from: https://stackoverflow.com/a/46604244
    #     for dirpath, _, filenames in os.walk(prj.config_root_dir):
    #         for filename in filenames:

    #             # Write the file named filename to the archive,
    #             # giving it the archive name 'arcname'.
    #             filepath = os.path.join(dirpath, filename)
    #             parentpath = os.path.relpath(filepath, prj.config_root_dir)
    #             arcname = os.path.join(
    #                 os.path.basename(prj.config_root_dir), parentpath
    #             )

    #             # omit mounts for permissions issues
    #             if parentpath.startswith("_mounts"):
    #                 continue

    #             zf.write(filepath, arcname)

    def import_data(self):
        raise NotImplementedError()

    def setup_env_from_file(self):
        raise NotImplementedError()

    def health_check(self, name: str):
        """Run a health check.

        :param name: Project name.
        :type name: str
        :raises NotImplemented: This function was not implemented yet.
        """
        raise NotImplementedError()
