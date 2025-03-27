import os
import re
import shutil
from pathlib import Path

from bson import ObjectId
from pymongo.database import Database

import fit_ctf_models.user_enrollment as _ue
from fit_ctf_models.cluster import ClusterConfig, ClusterConfigManager, Service
from fit_ctf_templates import (
    JINJA_TEMPLATE_DIRPATHS,
    get_template,
)
from fit_ctf_utils import get_or_create_logger
from fit_ctf_utils.constants import DEFAULT_STARTING_PORT
from fit_ctf_utils.container_client.container_client_interface import (
    ContainerClientInterface,
)
from fit_ctf_utils.exceptions import (
    ProjectExistsException,
    ProjectNamingFormatException,
    ProjectNotExistException,
    SSHPortOutOfRangeException,
)
from fit_ctf_utils.mongo_queries import MongoQueries
from fit_ctf_utils.types import (
    HealthCheckDict,
    ModuleCountDict,
    PathDict,
    ProjectPortListingDict,
    RawProjectDict,
)


class Project(ClusterConfig):
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
    max_nof_users: int
    starting_port_bind: int
    description: str = ""

    @property
    def max_port(self) -> int:
        return self.starting_port_bind + self.max_nof_users - 1


class ProjectManager(ClusterConfigManager[Project]):
    """A manager class that handles operations with `Project` objects."""

    def __init__(
        self, db: Database, c_client: type[ContainerClientInterface], paths: PathDict
    ):
        """Constructor method.

        :param db: A MongoDB database object.
        :type db: Database
        :param c_client: A container client class for calling container engine API.
        :type c_client: type[ContainerClientInterface]
        :param paths: A list of content paths.
        :type paths: PathDict
        """
        super().__init__(db, db["project"], c_client, paths)

    @property
    def _ue_mgr(self) -> "_ue.UserEnrollmentManager":
        """Returns a user enrollment manager.

        :return: A user enrollment manager initialized in ProjectManager.
        :rtype: _user_enroll.UserEnrollmentManager
        """
        return _ue.UserEnrollmentManager(self._db, self.c_client, self._paths)

    def get_doc_by_id(self, _id: ObjectId) -> Project | None:
        res = self._coll.find_one({"_id": _id})
        return Project(**res) if res else None

    def get_doc_by_id_raw(self, _id: ObjectId, projection: dict | None = None):
        projection = {} if projection is None else projection
        return self._coll.find_one({"_id": _id}, projection)

    def get_doc_by_filter(self, **kw) -> Project | None:
        res = self._coll.find_one(filter=kw)
        return Project(**res) if res else None

    def get_doc_by_filter_raw(
        self, filter: dict | None = None, projection: dict | None = None
    ):
        filter = {} if filter is None else filter
        projection = {} if projection is None else projection
        return self._coll.find_one(filter=filter, projection=projection)

    def get_docs(self, **filter) -> list[Project]:
        res = self._coll.find(filter=filter)
        return [Project(**data) for data in res]

    def create_and_insert_doc(self, **kw) -> Project:
        doc = Project(**kw)
        self.insert_doc(doc)
        return doc

    def get_project(
        self, project_or_name: str | Project, active: bool | None = True
    ) -> Project:
        """Retrieve project data from the database.

        If the given argument is a Project instance, it will simple return
        the argument.

        :param project_or_name: Project name or the instance.
        :type name: str | Project
        :param active: Fetch documents with the given active value. If set to None,
            the function fetches both active and inactive documents. Defaults to True.
        :type active: bool | None
        :raises ProjectNotExistException: Project data was not found in the database.
        :return: The retrieved project object.
        :rtype: Project
        """
        if isinstance(project_or_name, Project):
            return project_or_name
        name = project_or_name
        _filter: dict = {"name": name}
        if active is not None:
            _filter["active"] = active
        prj = self.get_doc_by_filter(**_filter)
        if not prj:
            raise ProjectNotExistException(f"Project `{name}` does not exist.")
        return prj

    def get_compose_file(self, project: Project) -> Path:
        """Return a path to the project's compose file.

        If the file does not exist it will be compiled.

        :param project: The project in question.
        :type project: Project
        :return: A path to the compose file.
        :rtype: Path
        """
        compose_file = self._paths["projects"] / project.name / "server_compose.yaml"
        if not compose_file.exists():
            self.compile_compose_file(project)
        return compose_file

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

        return lof_prjs[0]["starting_port_bind"] + lof_prjs[0]["max_nof_users"]

    def get_reserved_ports(self) -> list[ProjectPortListingDict]:
        """Get a list of reserved ports.

        :return: A list of reserved port ranges.
        :rtype: list[ProjectPortListingDict]
        """
        pipeline = MongoQueries.project_get_reserved_ports()
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

    def create_admin_service(self, project_name: str) -> Service:
        return Service(
            service_name="admin",
            module_name="base",
            is_local=True,
            networks={f"{project_name}_admin_net": {}},
        )

    def create_template_project_service(
        self,
        project: Project,
        service_name: str,
        module_name: str,
        is_local: bool,
    ) -> Service:
        return Service(
            service_name=service_name,
            module_name=module_name,
            is_local=is_local,
            networks={f"{project.name}_main_net": {}, f"{project.name}_admin_net": {}},
        )

    def get_modules_count(
        self, project_or_name: str | Project | None
    ) -> list[ModuleCountDict]:
        _filter: dict = {"active": True}
        if project_or_name:
            project = self.get_project(project_or_name)
            _filter["_id"] = project.id

        pipeline = [{"$match": _filter}, *MongoQueries.count_module_name_occurences()]
        return [i for i in self.collection.aggregate(pipeline)]

    def init_project(
        self,
        name: str,
        max_nof_users: int,
        starting_port_bind: int = -1,
        description: str = "",
        **kw,
    ) -> Project:
        if not self.validate_project_name(name):
            raise ProjectNamingFormatException(
                f"Given name `{name}` is not allowed. "
                "Only lowercase characters, underscore and numbers are allowed."
            )
        # check if project already exists
        prj = self.get_doc_by_filter(name=name, active=True)
        if prj:
            raise ProjectExistsException(f"Project `{name}` already exist.")

        if starting_port_bind < 0:
            starting_port_bind = self._get_available_starting_port()

        if starting_port_bind + max_nof_users > 65_535:
            raise SSHPortOutOfRangeException(
                "Not enough available ports."
            )  # pragma: no cover

        dest_dir = self._paths["projects"] / name
        dest_dir.mkdir(parents=True)

        (dest_dir / "users").mkdir()
        (dest_dir / "logs").mkdir()

        prj = self.create_and_insert_doc(
            name=name,
            max_nof_users=max_nof_users,
            starting_port_bind=starting_port_bind,
            description=description,
            services={"admin": self.create_admin_service(name)},
        )

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

        lof_user_enrolls = self._ue_mgr.get_docs_raw(
            filter={"project_id.$id": prj.id, "active": True},
            projection={"_id": 0, "container_port": 1, "forwarded_port": 1},
        )

        lof_cmd = [
            "firewall-cmd --zone=public "
            "--add-forward-port="
            f"port={i['forwarded_port']}:"
            "proto=tcp:"
            f"toport={i['container_port']}:"
            f"toaddr={dest_ip_addr}\n"
            for i in lof_user_enrolls
        ]

        with open(filename, "w") as f:
            f.write("#!/usr/bin/env bash\n\n")
            f.writelines(lof_cmd)
            f.write("firewall-cmd --zone=public --add-masquerade\n")
        os.chmod(filename, 0o755)

    def start_project_cluster(self, project_or_name: str | Project) -> int:
        """Boot the project server cluster.

        :param project_or_name: Project name or the instance.
        :type name: str | Project
        :return: An exit code.
        :rtype: int
        """
        project = self.get_project(project_or_name)
        return self.c_client.compose_up(
            get_or_create_logger(project.name), self.get_compose_file(project)
        )

    def restart_project_cluster(self, project_or_name: str | Project):
        """Restart project server cluster.

        :param project_or_name: Project name or the instance.
        :type name: str | Project
        :return: A completed process object.
        :rtype: subprocess.CompletedProcess
        """
        project = self.get_project(project_or_name)
        self.stop_project_cluster(project)
        self.start_project_cluster(project)

    def stop_project_cluster(self, project_or_name: str | Project) -> int:
        """Stop the project server cluster.

        :param project_or_name: Project name or the instance.
        :type name: str | Project
        :return: An exit code.
        :rtype: int
        """
        project = self.get_project(project_or_name)
        return self.c_client.compose_down(
            get_or_create_logger(project.name), self.get_compose_file(project)
        )

    def project_is_running(self, project_or_name: str | Project) -> bool:
        """Check if the project server is running.

        :param project_or_name: Project name or the instance.
        :type name: str | Project
        :return: Returns `True` if the server is running; `False` otherwise.
        :rtype: bool
        """
        project = self.get_project(project_or_name)
        return len(self.c_client.compose_ps(self.get_compose_file(project))) > 0

    def build_project_cluster_images(self, project_or_name: str | Project) -> int:
        """Rebuild project images.

        :param project_or_name: Project name or the instance.
        :type name: str | Project
        :return: An exit code.
        :rtype: int
        """
        project = self.get_project(project_or_name)
        return self.c_client.compose_build(
            get_or_create_logger(project.name), self.get_compose_file(project)
        )

    def compile_compose_file(self, project: Project):
        compose_filepath = (
            self._paths["projects"] / project.name / "server_compose.yaml"
        )
        with open(str(compose_filepath.resolve()), "w") as f:
            template = get_template(
                "server_compose.yaml.j2", str(JINJA_TEMPLATE_DIRPATHS["v1"].resolve())
            )
            f.write(
                template.render(
                    project=project.model_dump(),
                    module_dir=self._paths["modules"],
                    container_name_prefix=project.name,
                )
            )

    def shell_admin(self, project: Project):  # pragma: no cover
        """Shell user into the admin container.

        :param project: A project object.
        :type project: Project
        """
        self.c_client.compose_shell(self.get_compose_file(project), "admin", "bash")

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

    def get_all_services_info(self, project_or_name: str | Project) -> list[dict]:
        project = self.get_project(project_or_name)
        return self.c_client.project_stats(project.name)

    def health_check(self, project_or_name: str | Project) -> list[HealthCheckDict]:
        prj = self.get_project(project_or_name)
        return self.c_client.compose_states(self.get_compose_file(prj))

    def disable_project(self, project_or_name: str | Project):
        prj = self.get_project(project_or_name)

        # cancel all services
        self.stop_project_cluster(prj)
        self._ue_mgr.stop_all_user_clusters(prj)

        self.c_client.rm_networks(
            get_or_create_logger(prj.name), f"{prj.name}_main_net"
        )
        self.c_client.rm_networks(
            get_or_create_logger(prj.name), f"{prj.name}_admin_net"
        )
        self._ue_mgr.disable_multiple_enrollments(
            [(user, prj) for user in self._ue_mgr.get_user_enrollments_for_project(prj)]
        )

        prj.active = False
        self.update_doc(prj)

    def flush_project(self, project_or_name: str | Project):
        try:
            prj = self.get_project(project_or_name, None)
            if prj.active:
                raise ProjectExistsException("Cannot flush files of an active project.")
        except ProjectNotExistException as e:
            raise ProjectNotExistException(e)

        path = self._paths["projects"] / prj.name
        if path.exists():
            shutil.rmtree(path)

        self._ue_mgr.flush_multiple_enrollments(
            [
                (user, prj)
                for user in self._ue_mgr.get_user_enrollments_for_project(prj, True)
            ]
        )
        self.remove_doc_by_id(prj.id)

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

        self.disable_project(prj)
        self.flush_project(prj)

    def get_projects_raw(self, include_inactive: bool = False) -> list[RawProjectDict]:
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
        pipeline = MongoQueries.project_get_projects_raw(include_inactive)
        return [i for i in self.collection.aggregate(pipeline)]

    def delete_all(self):
        """Remove all projects from the host system and clear database."""
        projects = self.get_docs()
        for prj in projects:
            self.delete_project(prj)
