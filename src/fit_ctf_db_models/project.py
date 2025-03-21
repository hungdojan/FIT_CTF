from __future__ import annotations

import json
import logging
import os
import re
import shutil
import zipfile
from dataclasses import asdict, dataclass, field, fields
from distutils.dir_util import copy_tree
from pathlib import Path
from typing import Any

from bson import ObjectId
from pymongo.database import Database

import fit_ctf_db_models.user as _user
import fit_ctf_db_models.user_config as _user_config
from fit_ctf_backend import (
    DirNotEmptyException,
    ProjectNamingFormatException,
    ProjectNotExistException,
)
from fit_ctf_backend.constants import (
    DEFAULT_MODULE_BUILD_DIRNAME,
    DEFAULT_PROJECT_MODULE_PREFIX,
    DEFAULT_STARTING_PORT,
    DEFAULT_USER_MODULE_PREFIX,
)
from fit_ctf_backend.exceptions import (
    DirNotExistsException,
    ModuleExistsException,
    ModuleNotExistsException,
    ProjectExistsException,
)
from fit_ctf_db_models.base import Base, BaseManager
from fit_ctf_db_models.compose_objects import Module
from fit_ctf_templates import (
    TEMPLATE_DIRNAME,
    TEMPLATE_FILES,
    TEMPLATE_PATHS,
    get_template,
)
from fit_ctf_utils import get_or_create_logger
from fit_ctf_utils.container_client.base_container_client import BaseContainerClient

log = logging.getLogger()
CURR_FILE = os.path.realpath(__file__)


@dataclass(init=False)
class Project(Base):
    """A class that represents a project.

    :param name: Project's name.
    :type name: str
    :param config_root_dir: A directory containing all project configuration files.
    :type name: str
    :param volume_mount_dir: A path to a directory containing user volume objects.
    :type volume_mount_dir: str
    :param max_nof_users: Number of users that can enroll the project.
    :type max_nof_users: int
    :param starting_port_bind: A ssh port of the first enrolled user
    :type starting_port_bind: int
    :param description: A project description.
    :type description: str
    :param project_modules: List of project modules. Defaults to [].
    :type project_modules: dict[str, Module], optional
    :param user_modules: List of user modules. Defaults to [].
    :type user_modules: dict[str, Module], optional
    """

    name: str
    config_root_dir: str
    volume_mount_dirname: str
    compose_file: str
    max_nof_users: int
    starting_port_bind: int
    description: str = field(default="")
    project_modules: dict[str, Module] = field(default_factory=dict)
    user_modules: dict[str, Module] = field(default_factory=dict)

    def __init__(self, **kwargs):
        """Constructor method."""
        # set default values
        self.description = ""
        self.active = True
        self.project_modules = dict()
        self.user_modules = dict()
        # ignore extra fields
        names = set([f.name for f in fields(self)])
        for k, v in kwargs.items():
            if k in names:
                setattr(self, k, v)

    @property
    def compose_filepath(self) -> Path:
        """Reconstruct path to compose file.

        :return: Path to compose file.
        :rtype: Path
        """
        return Path(self.config_root_dir) / self.compose_file

    def get_project_module(self, module_name: str) -> Module:
        """Get a project module instance.

        :param module_name: Module name.
        :type module_name: str
        :raises ModuleNotExistsException: The given project does not contain selected module.
        :return: A retrieved module instance.
        :rtype: Module
        """
        module = self.project_modules.get(module_name)
        if not module:
            raise ModuleNotExistsException(
                f"The project `{self.name}` does not contain a module `{module_name}`."
            )
        return Module(**module)

    def get_user_module(self, module_name: str) -> Module:
        """Get a user module instance.

        :param module_name: Module name.
        :type module_name: str
        :raises ModuleNotExistsException: The given project does not contain selected module.
        :return: A retrieved module instance.
        :rtype: Module
        """
        module = self.user_modules.get(module_name)
        if not module:
            raise ModuleNotExistsException(
                f"The project `{self.name}` does not contain a module `{module_name}`."
            )
        return Module(**module)


class ProjectManager(BaseManager[Project]):
    """A manager class that handles operations with `Project` objects."""

    def __init__(self, db: Database, c_client: type[BaseContainerClient]):
        """Constructor method.

        :param db: A MongoDB database object.
        :type db: Database
        :param c_client: A container client class for calling container engine API.
        :type c_client: type[BaseContainerClient]
        """
        super().__init__(db, db["project"], c_client)

    @property
    def _uc_mgr(self) -> _user_config.UserConfigManager:
        """Returns a user config manager.

        :return: A user config manager initialized in ProjectManager.
        :rtype: _user_config.UserConfigManager
        """
        return _user_config.UserConfigManager(self._db, self.c_client)

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

    def get_project(self, name_or_project: str | Project) -> Project:
        """Retrieve project data from the database.

        If the given argument is a Project instance, it will simple return
        the argument.

        :param name_or_project: Project name or the instance.
        :type name: str | Project
        :raises ProjectNotExistException: Project data was not found in the database.
        :return: The retrieved project object.
        :rtype: Project
        """
        if isinstance(name_or_project, Project):
            return name_or_project
        name = name_or_project
        prj = self.get_doc_by_filter(name=name, active=True)
        if not prj:
            raise ProjectNotExistException(f"Project `{name}` does not exists.")
        return prj

    def get_active_users_for_project(
        self, project_or_name: str | Project
    ) -> list[_user.User]:
        """Return list of users that are enrolled to the project.

        :param project_or_name: Project name or a `Project` object.
        :type project_or_name: str | Project
        :raises ProjectNotExistException: Project data was not found in the database.
        :return: A list of enrolled users.
        :rtype: list[_user.User]
        """
        project = self.get_project(project_or_name)

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
        """Return list of users that are enrolled to the project.

        Returns a raw format of the output. The final dictionary has the following format:
            {
                **{
                    user data without password information
                },
                "forwarded_port": <forwarded_port>,
                "mount": <path_to_mount>
            }

        :param project_or_name: Project name or a `Project` object.
        :type project_or_name: str | Project
        :raises ProjectNotExistException: Project data was not found in the database.
        :return: A list of raw results.
        :rtype: list[dict[str, Any]]
        """
        project = self.get_project(project_or_name)

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
                    "pipeline": [
                        {
                            "$project": {
                                "config_root_dir": 1,
                                "_id": 0,
                                "volume_mount_dirname": 1,
                            }
                        }
                    ],
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
                        {"$project": {"password": 0, "shadow_hash": 0, "_id": 0}},
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
                        "$concat": [
                            "$project.config_root_dir",
                            "/",
                            "$project.volume_mount_dirname",
                            "/",
                            "$user.username",
                        ]
                    },
                }
            },
        ]

        return [
            #   vvvvvvvvvvvv -- spreading dict key-values
            {**i["user"], "mount": i["mount"], "forwarded_port": i["forwarded_port"]}
            for i in uc_coll.aggregate(pipeline)
        ]

    def _get_available_starting_port(self) -> int:
        """A function that calculates an available starting SSH port.

        :return: A vacant port.
        :rtype: int
        """
        # get sorted list of starting ports of all projects
        lof_prjs_cur = self._coll.find(
            filter={"active": True},
            projection={"_id": 0, "max_nof_users": 1, "starting_port_bind": 1},
        ).sort({"starting_port_bind": -1})
        lof_prjs = [i for i in lof_prjs_cur]

        if not lof_prjs:
            return DEFAULT_STARTING_PORT

        # calculate the next starting port, leave 1000 number in case reallocation will
        # be required later
        return lof_prjs[0]["starting_port_bind"] + lof_prjs[0]["max_nof_users"] + 1000

    def get_reserved_ports(self) -> list[dict[str, Any]]:
        """Get a list of reserved ports.

        The final directory has a following format:
        {
            "_id": <object_id>,
            "name": <project_name>,
            "min_port": <starting_port>,
            "max_port": <starting_port> + <max_nof_users>
        }

        :return: A list of reserved port ranges.
        :rtype: list[dict[str, Any]]
        """
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

    @staticmethod
    def validate_project_name(project_name: str) -> bool:
        """Validate the project name format.

        The username can only contain lowercase characters, underscore, or digits.

        :param username: A username to validate.
        :type username: str
        :return: `True` if given project name meets all the criteria.
        :rtype: bool
        """
        return re.search(r"^[a-z0-9_]*$", project_name) is not None

    def init_project(
        self,
        name: str,
        dest_dir: str,
        max_nof_users: int,
        starting_port_bind: int = -1,
        volume_mount_dirname: str = "_mounts",
        dir_name: str | None = "",
        description: str = "",
        compose_file: str = "server_compose.yaml",
    ) -> Project:
        """Create a project from a template.

        This function creates the following file structure:
            <dest_dir>
              -- <dir_name>
                  -- <compose_file>
                  -- <server_config>
                  -- _mounts
                      -- <home_volumes_for_each_user>
        Once the project is generated, the compose file is compiled.

        :param name: Project's name. The support format for the name is `^[a-z0-9_]*$`.
            Uppercase or special characters are not allowed.
        :type name: str
        :param dest_dir: A destination directory where project data will be stored.
        :type name: str
        :param max_nof_users: Number of users that can enroll the project.
        :type max_nof_users: int
        :param starting_port_bind: A ssh port of the first enrolled user. When
            -1 is set the function will automatically find and assign available
            port. Defaults to -1.
        :type starting_port_bind: int, optional
        :param volume_mount_dirname: A destination directory that will contain
            user mount directories/images. If the path does not exist, it will be
            create inside `dest_dir`. Defaults to "_mounts".
        :type volume_mount_dirname: str, optional
        :param dir_name: A project directory name. If not set function will
            auto-generate one. Defaults to `None`.
        :type dir_name: str | None, optional
        :param description: A project description. Defaults to "".
        :type description: str, optional
        :param compose_file: Name of the server nodes' compose file. Defaults to
            "server_compose.yaml".
        :type compose_file: str, optional

        :raises ProjectNamingFormatException: Project name does not follow the naming
            convention.
        :raises ProjectExistsException: Project with the given name already exist.
        :raises DirNotExistsException: A path to `dest_dir` does not exist.
        :raises DirNotExistsException: A `dest_dir` directory is not empty.

        :return: A created project object.
        :rtype: class `Project`
        """
        if not self.validate_project_name(name):
            raise ProjectNamingFormatException(
                f"Given name `{name}` is not allowed. "
                "Only lowercase characters, underscore and numbers are allowed."
            )
        # check if project already exists
        prj = self.get_doc_by_filter(name=name, active=True)
        if prj:
            raise ProjectExistsException(f"Project `{name}` already exist.")
        if not os.path.isdir(dest_dir):
            raise DirNotExistsException("A destination directory does not exists.")

        if starting_port_bind < 0:
            starting_port_bind = self._get_available_starting_port()

        if not dir_name:
            dir_name = name
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

        # store into the database
        prj = self.create_and_insert_doc(
            name=name,
            config_root_dir=str(destination.resolve()),
            compose_file=compose_file,
            max_nof_users=max_nof_users,
            starting_port_bind=starting_port_bind,
            description=description,
            volume_mount_dirname=volume_mount_dirname,
            user_modules={},
        )

        # create server_compose.yaml file
        self.compile_project(prj)

        return prj

    def generate_port_forwarding_script(
        self, project_or_name: str | Project, dest_ip_addr: str, filename: str
    ):
        """Generate a port forwarding script.

        :param project_name: Project name or the instance.
        :type project_name: str | Project
        :param dest_ip_addr: IP address of the destination machine/server.
        :type dest_ip_addr: str
        :param filename: And output filename.
        :type filename: str
        :raises ProjectNotExistException: Project data were not found in the database.
        """
        prj = self.get_project(project_or_name)

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
        os.chmod(filename, 0o755)

    def start_project(self, project: Project) -> int:
        """Boot the project server.

        Run `podman-compose up` in the sub-shell.

        :param project: A project object.
        :type project: Project
        :return: An exit code.
        :rtype: int
        """
        return self.c_client.compose_up(
            get_or_create_logger(project.name), project.compose_filepath
        )

    def restart_project(self, project: Project):
        """Restart project server.

        Run `podman-compose up` in the sub-shell.

        :param project: A project object.
        :type project: Project
        :return: A completed process object.
        :rtype: subprocess.CompletedProcess
        """
        self.stop_project(project)
        self.start_project(project)

    def stop_project(self, project: Project) -> int:
        """Stop the project server.

        Run `podman-compose down` in the sub-shell.

        :param project: A project object.
        :type project: Project
        :return: An exit code.
        :rtype: int
        """
        return self.c_client.compose_down(
            get_or_create_logger(project.name), project.compose_filepath
        )

    def project_is_running(self, project: Project) -> bool:
        """Check if the project server is running.

        :param project: A project object.
        :type project: Project
        :return: Returns `True` if the server is running; `False` otherwise.
        :rtype: bool
        """
        return len(self.c_client.compose_ps(project.compose_filepath)) > 0

    def build_project(self, project: Project) -> int:
        """Rebuild project images.

        Run `podman-compose down` in the sub-shell.

        :param project: A project object.
        :type project: Project
        :return: An exit code.
        :rtype: int
        """

        return self.c_client.compose_build(
            get_or_create_logger(project.name), project.compose_filepath
        )

    def compile_project(self, project: Project):
        """Compile a compose file.

        :param project: A project object.
        :type project: Project
        """
        # create server_compose.yaml file
        compose_filepath = Path(project.config_root_dir) / project.compose_file
        with open(str(compose_filepath), "w") as f:
            template = get_template(
                TEMPLATE_FILES["server_compose"], project.config_root_dir
            )
            f.write(template.render(project=asdict(project), user={}))

    def shell_admin(self, project: Project):  # pragma: no cover
        """Shell user into the admin container.

        :param project: A project object.
        :type project: Project
        """
        self.c_client.compose_shell(str(project.compose_filepath), "admin", "bash")

    def get_resource_usage(
        self, project_or_name: str | Project
    ) -> list[dict[str, str]]:
        """Get project resource usage using `podman-compose` command.

        :param project_name: Project name or the instance.
        :type project_name: str | Project
        :raises ProjectNotExistException: Project data were not found in the database.
        :return: List of each pod statistics.
        :rtype: list[dict[str, str]]
        """
        prj = self.get_project(project_or_name)
        return self.c_client.stats(prj.name)

    def get_ps_data(self, project_or_name: str | Project) -> list[str]:
        """Get running containers of a project using `podman` command.

        :param project_name: Project name or the instance.
        :type project_name: str | Project
        :raises ProjectNotExistException: Project data were not found in the database.
        :return: List of stdout.
        :rtype: list[str]
        """
        prj = self.get_project(project_or_name)
        return self.c_client.ps(prj.name)

    def export_project(self, project_or_name: str | Project, output_file: str):
        """Export project configuration files.

        Generate a ZIP archive.

        :param project_name: Project name or the instance.
        :type project_name: str | Project
        :param output_file: Output filename.
        :type output_file: str
        :raises ProjectNotExistException: Project was not found.
        """
        prj = self.get_project(project_or_name)
        with zipfile.ZipFile(output_file, "w", zipfile.ZIP_DEFLATED) as zf:
            # add a file containing list of enrolled users
            zf.writestr(
                "enrolled_users.json",
                json.dumps(self.get_active_users_for_project_raw(prj)),
            )

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

                    # omit mounts for permissions issues
                    if parentpath.startswith("_mounts"):
                        continue

                    zf.write(filepath, arcname)

    def delete_project(self, project_or_name: str | Project):
        """Delete a project.

        :param project_name: Project name or the instance.
        :type project_name: str | Project
        """
        # also deletes everything
        try:
            prj = self.get_project(project_or_name)
        except ProjectNotExistException:
            # TODO: log that project does not exist
            return

        # stop project if running
        if self.project_is_running(prj):
            self.stop_project(prj)

        # cancel all users enrollments
        self._uc_mgr.stop_all_user_instances(prj)
        self._uc_mgr.cancel_all_project_enrollments(prj)

        self.c_client.rm_images(get_or_create_logger(prj.name), f"{prj.name}_")
        self.c_client.rm_networks(get_or_create_logger(prj.name), f"{prj.name}_")

        # remove everything from the directory
        shutil.rmtree(prj.config_root_dir)
        prj.active = False
        self.update_doc(prj)

    def get_projects(self, include_inactive: bool = False) -> list[dict[str, Any]]:
        """Get list of all projects.

        The final directory has the following format:
        {
            "name": <project_name>,
            "max_nof_users": <max_nof_users>,
            "active_users": <nof_active_users>,
            "active": <active_status>
        }

        :param include_inactive: When `True` is set, function will also return `inactive`
        projects, defaults to False.
        :type include_inactive: bool, optional
        :return: A list of found projects in raw format.
        :rtype: list[dict[str, Any]]
        """
        _filter = {}
        if not include_inactive:
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

    def delete_all(self):
        """Remove all projects from the host system and clear database."""
        projects = self.get_projects()
        for prj in projects:
            self.delete_project(prj["name"])
        self.remove_docs_by_filter()

    # MANAGE MODULES
    def create_project_module(
        self, project_or_name: str | Project, module_name: str
    ) -> Module:
        """Create a new project module.

        :param project_name: Project name or the instance.
        :type project_name: str | Project
        :param module_name: Module name.
        :type module_name: str
        :raises ProjectNotExistException: Project was not found.
        :raises ModuleExistsException: Module with the given name already exists.
        :raises DirNotEmptyException: Given directory is not empty.
        :return: Created instance of module object.
        :rtype: Module
        """
        project = self.get_project(project_or_name)
        if module_name in project.project_modules:
            raise ModuleExistsException(
                f"Project `{project.name}` already has `{module_name}` module."
            )

        # create a destination directory and check if exists
        module_root_dir = f"_modules/{DEFAULT_PROJECT_MODULE_PREFIX}{module_name}"
        module_dst = Path(project.config_root_dir) / module_root_dir
        os.makedirs(module_dst, exist_ok=True)
        if len(os.listdir(module_dst)) > 0:
            raise DirNotEmptyException(
                f"Destination directory `{module_dst}` is not empty."
            )

        # fill directory with templates
        copy_tree(TEMPLATE_PATHS["project_module"], str(module_dst))

        module = Module(
            name=module_name,
            root_dir=module_root_dir,
            build_dir_name=DEFAULT_MODULE_BUILD_DIRNAME,
            compose_template_path=TEMPLATE_FILES["module_compose"],
        )
        project.project_modules[module_name] = module
        self.update_doc(project)
        # TODO: compile
        return module

    def list_project_modules(self, project_or_name: str | Project) -> list[Module]:
        """Get a list of project modules.

        :param project_name: Project name or the instance.
        :type project_name: str | Project
        :raises ProjectNotExistException: Project was not found.
        :return: A list of found modules.
        :rtype: list[Module]
        """
        project = self.get_project(project_or_name)
        return [Module(**m) for m in list(project.project_modules.values())]

    def remove_project_module(self, project_or_name: str | Project, module_name: str):
        """Remove a project module from the project.

        After the successful removal the compose file will be automatically recompiled.

        :param project_name: Project name or the instance.
        :type project_name: str | Project
        :param module_name: Module name.
        :type module_name: str
        :raises ProjectNotExistException: Project was not found.
        :raises ModuleNotExistsException: Module with given name was not found.
        """
        project = self.get_project(project_or_name)

        if module_name not in project.project_modules:
            raise ModuleNotExistsException(
                f"Module `{module_name}` was not found in `{project.name}`."
            )

        # TODO: dataclasses cannot deserialize nested objects
        module_info = Module(**project.project_modules.pop(module_name))
        module_path = Path(project.config_root_dir) / module_info.root_dir
        if module_path.exists():
            shutil.rmtree(module_path)
        self.update_doc(project)
        self.compile_project(project)

    def create_user_module(
        self, project_or_name: str | Project, module_name: str
    ) -> Module:
        """Create a new user module.

        :param project_name: Project name or the instance.
        :type project_name: str | Project
        :param module_name: Module name.
        :type module_name: str
        :raises ProjectNotExistException: Project was not found.
        :raises ModuleExistsException: Module with the given name already exists.
        :raises DirNotEmptyException: Given directory is not empty.
        :return: Created instance of module object.
        :rtype: Module
        """
        project = self.get_project(project_or_name)
        if module_name in project.user_modules:
            raise ModuleExistsException(
                f"Project `{project.name}` already has `{module_name}` module."
            )

        # create a destination directory and check if exists
        module_root_dir = f"_modules/{DEFAULT_USER_MODULE_PREFIX}{module_name}"
        module_dst = Path(project.config_root_dir) / module_root_dir
        os.makedirs(module_dst, exist_ok=True)
        if len(os.listdir(module_dst)) > 0:
            raise DirNotEmptyException(
                f"Destination directory `{module_dst}` is not empty."
            )

        # fill directory with templates
        copy_tree(TEMPLATE_PATHS["user_module"], str(module_dst))

        module = Module(
            name=module_name,
            root_dir=module_root_dir,
            build_dir_name=DEFAULT_MODULE_BUILD_DIRNAME,
            compose_template_path=TEMPLATE_FILES["module_compose"],
        )
        project.user_modules[module_name] = module
        self.update_doc(project)
        return module

    def list_user_modules(self, project_or_name: str | Project) -> list[Module]:
        """Get a list of user modules.

        :param project_name: Project name or the instance.
        :type project_name: str | Project
        :raises ProjectNotExistException: Project was not found.
        :return: A list of found modules.
        :rtype: list[Module]
        """
        project = self.get_project(project_or_name)
        return [Module(**m) for m in list(project.user_modules.values())]

    def remove_user_module(self, project_or_name: str | Project, module_name: str):
        """Remove a user module from the project.

        After the successful removal the compose file will be automatically recompiled.

        :param project_name: Project name or the instance.
        :type project_name: str | Project
        :param module_name: Module name.
        :type module_name: str
        :raises ProjectNotExistException: Project was not found.
        :raises ModuleNotExistsException: Module with given name was not found.
        """
        project = self.get_project(project_or_name)

        if module_name not in project.user_modules:
            raise ModuleNotExistsException(
                f"Module `{module_name}` was not found in `{project.name}`."
            )

        # remove from all users
        lof_users = self.get_active_users_for_project(project)
        for user in lof_users:
            self._uc_mgr.remove_module(user, project, module_name)
        module_info = Module(**project.user_modules.pop(module_name))
        module_path = Path(project.config_root_dir) / module_info.root_dir
        if module_path.exists():
            shutil.rmtree(module_path)
        self.update_doc(project)
