import os
import tempfile
import zipfile
from pathlib import Path
from shutil import copytree
from typing import Literal, cast

import pymongo
from jsonschema.exceptions import ValidationError
from pymongo.database import Database

import fit_ctf_models.project as project
from fit_ctf_models import (
    ProjectManager,
    UserEnrollmentManager,
    UserManager,
)
from fit_ctf_models.cluster import Service
from fit_ctf_models.module_manager import ModuleManager
from fit_ctf_utils import get_c_client_by_name
from fit_ctf_utils import log_print as log
from fit_ctf_utils.auth.auth_interface import AuthInterface
from fit_ctf_utils.constants import DEFAULT_PASSWORD_LENGTH
from fit_ctf_utils.data_parser.yaml_parser import YamlParser
from fit_ctf_utils.exceptions import (
    CTFException,
    ImportFileCorruptedException,
    ProjectExistsException,
    UserExistsException,
)
from fit_ctf_utils.mongo_queries import MongoQueries
from fit_ctf_utils.types import DatabaseDumpDict, NewUserDict, PathDict, SetupDict


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

        self.c_client = get_c_client_by_name(os.getenv("CONTAINER_CLIENT", ""))
        self._managers = {
            "project": ProjectManager(self._ctf_db, self.c_client, paths),
            "user": UserManager(self._ctf_db, self.c_client, paths),
            "user_enrollment": UserEnrollmentManager(
                self._ctf_db, self.c_client, paths
            ),
            "module": ModuleManager(self._ctf_db, self.c_client, paths),
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

    @property
    def module_mgr(self) -> ModuleManager:
        """Returns a user enrollment manager.

        :return: A user enrollment manager initialized in CTFManager.
        :rtype: UserEnrollmentManager
        """
        return self._managers["module"]

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

        self.init_tool()

    def init_tool(self, base_image_os: Literal["rhel", "ubuntu"] = "rhel"):
        """Initialize base images."""
        for module_name in {"base", "base_ssh"}:
            if not (self._paths["modules"] / module_name).exists():
                dst_path = self._paths["modules"] / module_name
                root_dir = (
                    Path(os.path.dirname(os.path.realpath(__file__))).parent.parent
                    / "config"
                    / "base_images"
                )

                if base_image_os not in {"rhel", "ubuntu"}:
                    raise ValueError(
                        "The only supported base image OS are `rhel` or `ubuntu`."
                    )
                src_path = root_dir / f"{module_name}_{base_image_os}"
                copytree(str(src_path.resolve()), str(dst_path.resolve()))

    def export_all(self, output_zip_name: str):
        raise NotImplementedError()

    def _load_all_data_to_dict(self, project: "project.Project") -> dict:
        data = {}
        data["project"] = {k: v for k, v in project.model_dump().items() if k != "_id"}

        users = self.user_enrollment_mgr.get_user_enrollments_for_project(project, True)
        data["users"] = [
            {k: v for k, v in u.model_dump().items() if k != "_id"} for u in users
        ]
        pipeline = MongoQueries.export_user_enrollments(project)
        data["enrollments"] = list(
            self.user_enrollment_mgr.collection.aggregate(pipeline)
        )

        module_count = self.module_mgr.reference_count(project.name)
        data["modules"] = [k for k, v in module_count.items() if v > 0]
        return data

    def _add_user_files_to_zipfile(self, zf: zipfile.ZipFile, data: dict):
        for username in [u["username"] for u in data["users"]]:
            # get path to shadow file
            user_root_dir = self._paths["users"] / username
            filepath = user_root_dir / "shadow"
            parentpath = os.path.relpath(filepath, user_root_dir)
            arcname = os.path.join(self._paths["users"].name, username, parentpath)

            # add a shadow file to the archive
            zf.write(filepath, arcname)

            # create an empty home directory
            zf.writestr(
                zipfile.ZipInfo(
                    os.path.join(self._paths["users"].name, username, "home/")
                ),
                "",
            )

    def _add_module_files_to_zipfile(self, zf: zipfile.ZipFile, data: dict):
        module_root_dir = self._paths["modules"]
        for module_name in data["modules"]:
            for dirpath, _, filenames in os.walk(module_root_dir / module_name):
                for filename in filenames:

                    # Write the file named filename to the archive,
                    # giving it the archive name 'arcname'.
                    # filepath = os.path.join(dirpath, filename)
                    filepath = Path(dirpath) / filename
                    parentpath = os.path.relpath(
                        filepath, module_root_dir / module_name
                    )
                    arcname = os.path.join(
                        self._paths["modules"].name,
                        os.path.basename(module_root_dir / module_name),
                        parentpath,
                    )

                    zf.write(filepath, arcname)

    def export_project(self, project_name: str, output_zip_name: str):
        """Export project configuration files.

        Generate a ZIP archive.

        :param project_name: Project name or the instance.
        :type project_name: str | Project
        :param output_file: Output filename.
        :type output_file: str
        :raises ProjectNotExistException: Project was not found.
        """
        project = self.prj_mgr.get_project(project_name)
        data = self._load_all_data_to_dict(project)

        with zipfile.ZipFile(output_zip_name, "w", zipfile.ZIP_DEFLATED) as zf:
            # add database dump
            zf.writestr("database_dump.yaml", YamlParser.dump_data(data))
            self._add_user_files_to_zipfile(zf, data)
            self._add_module_files_to_zipfile(zf, data)

    def _validate_with_database(self, data: DatabaseDumpDict):
        # check if they exist in the database, raise collision error if needed
        project = data["project"]
        if self.prj_mgr.get_doc_by_filter(name=project["name"]):
            raise ProjectExistsException(f"Project `{project['name']}` already exists.")
        modules = list(self.module_mgr.list_modules().keys())
        for module_name in data["modules"]:
            if module_name in modules:
                log.warning(f"Module `{module_name}` is already present on the host.")
        usernames = [
            user["username"]
            for user in self.user_mgr.get_docs_raw(
                filter={
                    "username": {"$in": [user["username"] for user in data["users"]]}
                },
                projection={"_id": 0, "username": 1},
            )
        ]
        if usernames:
            raise UserExistsException(
                f"Users `{' '.join(usernames)}` already exist in the database."
            )

    def _add_to_database(self, data: DatabaseDumpDict):
        prj = self.prj_mgr.init_project(
            data["project"]["name"],
            data["project"]["max_nof_users"],
            description=data["project"]["description"],
        )
        self.prj_mgr.remove_service(prj, "admin")
        for name, service in data["project"]["services"].items():
            self.prj_mgr.register_service(prj, name, Service(**service))

        for user in data["users"]:
            self.user_mgr.create_and_insert_doc(**user)

        for enrollment in data["enrollments"]:
            user = enrollment["user"]
            project = enrollment["project"]
            user_enroll = self.user_enrollment_mgr.enroll_user_to_project(user, project)
            self.user_enrollment_mgr.remove_service(user_enroll, "login")
            for name, service in enrollment["services"].items():
                self.user_enrollment_mgr.register_service(
                    user_enroll, name, Service(**service)
                )

    def import_project(self, input_file: Path):
        with tempfile.TemporaryDirectory() as tempdir:
            dir_path = Path(tempdir)
            with zipfile.ZipFile(input_file, "r") as zf:
                if "database_dump.yaml" not in zf.namelist():
                    raise ImportFileCorruptedException(
                        "Missing `database_dump.yaml` file in the zip."
                    )

                with zf.open("database_dump.yaml") as f:
                    try:
                        data = cast(
                            DatabaseDumpDict,
                            YamlParser.load_data_stream(f, "database_dump"),
                        )
                    except ValidationError as e:
                        raise ImportFileCorruptedException(
                            "File `database_dump.yaml` does not match the schema.\n"
                            f"{str(e)}"
                        )

                # process data
                self._validate_with_database(data)
                self._add_to_database(data)

                # extract files into the temporary directory
                zf.extractall(dir_path)

                # move all the files to the designated places
                for item in (dir_path / "user").iterdir():
                    copytree(item, self._paths["users"] / item.name)
                for item in (dir_path / "module").iterdir():
                    if not (self._paths["modules"] / item.name).exists():
                        copytree(item, self._paths["modules"] / item.name)

    def _dry_run_setup(self, data: SetupDict):
        out = {}
        if data.get("projects"):
            project_names = [prj["name"] for prj in data["projects"]]
            found_names = [
                prj["name"]
                for prj in self.prj_mgr.get_docs_raw(
                    {"name": {"$in": project_names}}, {"_id": 0, "name": 1}
                )
            ]
            new_names = set(project_names).difference(set(found_names))
            if new_names:
                out["new_projects"] = list(new_names)

        if data.get("users"):
            user_names = [user["username"] for user in data["users"]]
            found_names = [
                user["username"]
                for user in self.user_mgr.get_docs_raw(
                    {"username": {"$in": user_names}}, {"_id": 0, "username": 1}
                )
            ]
            new_names = set(user_names).difference(set(found_names))
            if new_names:
                out["new_users"] = list(new_names)
        if out:
            log.info(YamlParser.dump_data(out))

    def _run_setup(self, data: SetupDict, exist_ok: bool) -> list[NewUserDict]:
        new_users = []
        if data.get("projects"):
            for prj in data["projects"]:
                try:
                    self.prj_mgr.init_project(**prj)
                except ProjectExistsException as e:
                    if exist_ok:
                        log.warning(e)
                        continue
                    raise ProjectExistsException(e)

        if data.get("users"):
            for user in data["users"]:
                try:
                    if user.get("generate_password"):
                        password = AuthInterface.generate_password(
                            DEFAULT_PASSWORD_LENGTH
                        )
                        _, user_data = self.user_mgr.create_new_user(
                            **user, password=password
                        )
                    else:
                        _, user_data = self.user_mgr.create_new_user(**user)
                except UserExistsException as e:
                    if exist_ok:
                        log.warning(e)
                        continue
                    raise UserExistsException(e)
                new_users.append(user_data)
        if data.get("enrollments"):
            for enroll in data["enrollments"]:
                try:
                    self.user_enrollment_mgr.enroll_user_to_project(
                        enroll["user"], enroll["project"]
                    )
                except CTFException as e:
                    if exist_ok:
                        log.warning(e)
                        continue
                    raise CTFException(e)
        return new_users

    def setup_env_from_file(
        self, file: Path, exist_ok: bool = False, dry_run: bool = False
    ) -> list[NewUserDict]:
        data: SetupDict = cast(SetupDict, YamlParser.load_data_file(file, "setup"))
        if dry_run:
            self._dry_run_setup(data)
            return []
        return self._run_setup(data, exist_ok)

    def uninstall(self):
        raise NotImplementedError()
