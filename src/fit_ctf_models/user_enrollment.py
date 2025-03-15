import logging
from pathlib import Path
from typing import Any

from bson import DBRef, ObjectId
from pydantic import Field
from pymongo.database import Database

import fit_ctf_models.project as _project
import fit_ctf_models.user as _user
from fit_ctf_models.base import Base, BaseManagerInterface
from fit_ctf_models.cluster import ClusterConfig, Service
from fit_ctf_templates import JINJA_TEMPLATE_DIRPATHS, get_template
from fit_ctf_utils import get_or_create_logger
from fit_ctf_utils.container_client.container_client_interface import (
    ContainerClientInterface,
)
from fit_ctf_utils.exceptions import (
    MaxUserCountReachedException,
    PortUsageCollisionException,
    SSHPortOutOfRangeException,
    UserEnrolledToProjectException,
    UserNotEnrolledToProjectException,
)
from fit_ctf_utils.mongo_queries import MongoQueries
from fit_ctf_utils.types import (
    HealthCheckDict,
    ModuleCount,
    PathDict,
    RawEnrolledProjects,
)

log = logging.getLogger()


class UserEnrollment(Base, ClusterConfig):
    """A class that represents a user enrollment document.

    It serves as a connections between the project and the user. When a user enrolls to a
    project a new `user_enrollment` document is created.

    :param user_id: A reference object that indicates a connection between a user and this
        document.
    :type user_id: DBRef
    :param project_id: A reference object that indicates a connection between a project
        and this document.
    :type project_id: DBRef
    :param container_port: An SSH port used to connect to login node.
    :type container_port: int
    :param forwarded_port: A forwarded port that user will connect to the outer server.
    :type forwarded_port: int
    :param modules: A collection of active modules that will start together with login
        node.
    :type modules: dict[str, Module]
    """

    user_id: DBRef
    project_id: DBRef
    container_port: int
    forwarded_port: int
    progress: dict = Field(default_factory=dict)

    def validate_dict(self) -> dict[str, Any]:
        model = super().validate_dict()
        model["user_id"] = {
            "$id": str(model["user_id"]["$id"]),
            "$ref": model["user_id"]["$ref"],
        }
        return model


class UserEnrollmentManager(BaseManagerInterface[UserEnrollment]):
    """A manager class that handles operations with `UserEnrollment` objects."""

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
        super().__init__(db, db["user_enrollment"], c_client, paths)

    @property
    def _prj_mgr(self) -> "_project.ProjectManager":
        """Returns a project manager.

        :return: A project manager initialized in UserEnrollmentManager.
        :rtype: _project.ProjectManager
        """
        return _project.ProjectManager(self._db, self.c_client, self._paths)

    @property
    def _user_mgr(self) -> "_user.UserManager":
        """Returns a user manager.

        :return: A user manager initialized in UserEnrollmentManager.
        :rtype: _user.UserManager
        """
        return _user.UserManager(self._db, self.c_client, self._paths)

    def _get_user_and_project(
        self,
        user_or_username: "str | _user.User",
        project_or_name: "str | _project.Project",
    ) -> tuple[_user.User, "_project.Project"]:
        """Retrieve both `User` and `Project` objects.

        :param user_or_username: User username or user object.
        :type user_or_username: str | _user.User
        :param project_or_name: Project name or project object.
        :type project_or_name: str | _project.Project
        :raises UserNotExistsException: User with the given username was not found.
        :raises ProjectNotExistException: Project data was not found in the database.
        :return: A found pair of `User` and `Project` objects.
        :rtype: tuple[_user.User, _project.Project]
        """
        return self._get_user(user_or_username), self._get_project(project_or_name)

    def _get_user(self, user_or_username: "str | _user.User") -> _user.User:
        """Get a user from the username or user object.

        :param user_or_username: Username or a user object.
        :type user_or_username: str | _user.User
        :raises UserNotExistsException: User with the given username was not found.
        :return: User with the given name, or the same object that was passed into the
            function.
        :rtype: _user.User
        """
        return self._user_mgr.get_user(user_or_username)

    def _get_project(
        self, project_or_name: "str | _project.Project"
    ) -> "_project.Project":
        """Get a project from the project name or project object.

        :param project_or_name: Project name or a project object.
        :type project_or_name: str | _project.Project
        :raises ProjectNotExistException: Project data was not found in the database.
        :return: Found project or passed project object.
        :rtype: _project.Project
        """
        return self._prj_mgr.get_project(project_or_name)

    def user_is_enrolled_to_project(
        self, user: "_user.User", project: "_project.Project"
    ) -> bool:
        """Check if user is enrolled to the given project.

        :param user: User object.
        :type user: str
        :param project: Project object.
        :type project: str
        :return: `True` if there is a user enrollment document that links the project with
            the given user.
        :rtype: bool
        """
        user_enrollment = self.get_doc_by_filter(
            **{"user_id.$id": user.id, "project_id.$id": project.id, "active": True}
        )
        return user_enrollment is not None

    def get_user_enrollment(
        self, user: _user.User, project: "_project.Project"
    ) -> UserEnrollment:
        """Get a user enrollment document.

        :param user: User object.
        :type user: _user.User
        :param project: Project object.
        :type project: _project.Project
        :raises UserNotEnrolledToProjectException: Given user is not enrolled to the
            project.
        :return: The found user enrollment document.
        :rtype: UserEnrollment
        """
        user_enrollment = self.get_doc_by_filter(
            **{"user_id.$id": user.id, "project_id.$id": project.id, "active": True}
        )
        if not user_enrollment:
            raise UserNotEnrolledToProjectException(
                f"User `{user.username}` is not assigned to the project `{project.name}`."
            )
        return user_enrollment

    def get_min_available_sshport(self, project: "_project.Project") -> int:
        user_enrollments = (
            self._coll.find(
                filter={"project_id.$id": project.id},
                projection={"_id": 0, "container_port": 1},
            )
            .sort({"container_port": -1})
            .limit(1)
        )
        res = [uc["container_port"] for uc in user_enrollments]
        if res:
            return res[0] + 1
        return project.starting_port_bind

    def get_doc_by_id(self, _id: ObjectId) -> UserEnrollment | None:
        res = self._coll.find_one({"_id": _id})
        return UserEnrollment(**res) if res else None

    def get_doc_by_id_raw(self, _id: ObjectId, projection: dict | None = None):
        projection = {} if projection is None else projection
        return self._coll.find_one({"_id": _id}, projection=projection)

    def get_doc_by_filter(self, **kw) -> UserEnrollment | None:
        res = self._coll.find_one(filter=kw)
        return UserEnrollment(**res) if res else None

    def get_doc_by_filter_raw(
        self, filter: dict | None = None, projection: dict | None = None
    ):
        filter = {} if filter is None else filter
        projection = {} if projection is None else projection
        return self._coll.find_one(filter=filter, projection=projection)

    def get_docs(self, **filter) -> list[UserEnrollment]:
        res = self._coll.find(filter=filter)
        return [UserEnrollment(**data) for data in res]

    def create_and_insert_doc(self, **kw) -> UserEnrollment:
        doc = UserEnrollment(**kw)
        self._coll.insert_one(doc.model_dump())
        return doc

    def compile_compose_file(
        self,
        user: "_user.User",
        project: "_project.Project",
    ):
        """Generate the compile file from the template."""
        ue = self.get_user_enrollment(user, project)
        compose_file = (
            self._paths["projects"]
            / project.name
            / "users"
            / f"{user.username}_compose.yaml"
        )

        with open(str(compose_file.resolve()), "w") as f:
            template = get_template(
                "user_compose.yaml.j2", str(JINJA_TEMPLATE_DIRPATHS["v1"].resolve())
            )
            f.write(
                template.render(
                    project=project.model_dump(),
                    user=user.model_dump(),
                    user_enrollment=ue.model_dump(),
                    module_dir=self._paths["modules"],
                    container_name_prefix=user.username,
                )
            )

    def get_compose_file(
        self,
        user_or_username: "str | _user.User",
        project_or_name: "str | _project.Project",
    ) -> Path:
        user, project = self._get_user_and_project(user_or_username, project_or_name)

        try:
            self.get_user_enrollment(user, project)
        except UserNotEnrolledToProjectException as e:
            raise UserNotEnrolledToProjectException(e)

        compose_file = (
            self._paths["projects"]
            / project.name
            / "users"
            / f"{user.username}_compose.yaml"
        )
        if not compose_file.exists():
            self.compile_compose_file(user, project)
        return compose_file

    def filter_users_not_in_project(
        self, project_or_name: "str | _project.Project", lof_usernames: list[str]
    ):
        prj = self._get_project(project_or_name)
        users = self.get_user_enrollments_for_project(prj)
        return list(
            set(lof_usernames).difference(set([user.username for user in users]))
        )

    def create_base_user_service(
        self, user: "_user.User", project: "_project.Project", container_port: int
    ) -> Service:
        user_home_dirpath = self._paths["users"] / user.username / "home"
        shadow_path = self._paths["users"] / user.username / "shadow"
        return Service(
            service_name="login",
            module_name="base_ssh",
            is_local=True,
            ports=[f"{container_port}:22"],
            networks={
                f"{project.name}_{user.username}_private_net": {},
                f"{project.name}_main_net": {},
            },
            volumes=[
                f"{str(user_home_dirpath.resolve())}:/home/user:Z",
                f"{str(shadow_path.resolve())}:/etc/shadow:Z",
            ],
        )

    def create_template_user_service(
        self,
        user: "_user.User",
        project: "_project.Project",
        service_name: str,
        module_name: str,
        is_local: bool,
    ) -> Service:
        return Service(
            service_name=service_name,
            module_name=module_name,
            is_local=is_local,
            networks={f"{project.name}_{user.username}_private_net": {}},
        )

    # ASSIGN USER TO PROJECTS

    def enroll_user_to_project(
        self,
        user_or_username: "str | _user.User",
        project_or_name: "str | _project.Project",
        container_port: int = -1,
        forwarded_port: int = -1,
    ) -> UserEnrollment:
        """Enroll user to the project.

        :param username: User username.
        :type username: str
        :param project_name: Project name.
        :type project_name: str
        :param container_port: An SSH port of the login node. If set to `-1` the function will
            autogenerate a value. Defaults to -1.
        :type container_port: int, optional
        :param forwarded_port: A forwarded port for the user to connect to the outer
            server. If set to `-1` the function will autogenerate a value. Defaults to -1.
        :type forwarded_port: int, optional
        :raises UserNotExistsException: User with the given username was not found.
        :raises ProjectNotExistException: Project data was not found in the database.
        :raise UserEnrolledToProjectException: The user is already enrolled to the project.
        :raises MaxUserCountReachedException: Project has already reached the maximum
            number of enrolled users.
        :raises PortUsageCollisionException: The port is already in use.
        :return: A created `UserEnrollment` object.
        :rtype: UserEnrollment
        """
        user, project = self._get_user_and_project(user_or_username, project_or_name)
        users = self.get_user_enrollments_for_project_raw(project)
        user_enrollment = self.get_doc_by_filter(
            **{"user_id.$id": user.id, "project_id.$id": project.id, "active": True}
        )

        if user_enrollment:
            raise UserEnrolledToProjectException(
                f"The user `{user.username}` is already enrolled to `{project.name}`"
            )

        if len(users) >= project.max_nof_users:
            raise MaxUserCountReachedException(
                f"Project `{project.name}` has already reached the maximum number of users."
            )

        if container_port < 0:
            container_port = self.get_min_available_sshport(project)

        if forwarded_port < 0:
            forwarded_port = container_port

        collision_test = [
            i
            for i in self._coll.aggregate(
                MongoQueries.user_enrollment_port_collision(
                    forwarded_port, container_port
                )
            )
        ]
        if collision_test:
            raise PortUsageCollisionException(
                f"Either forwarded port `{forwarded_port}` or system port `{container_port}`"
                "is already in use by another user in the project."
            )

        user_enrollment = self.create_and_insert_doc(
            user_id=DBRef("user", user.id),
            project_id=DBRef("project", project.id),
            container_port=container_port,
            forwarded_port=forwarded_port,
            services={
                "base": self.create_base_user_service(user, project, container_port)
            },
        )
        return user_enrollment

    def enroll_multiple_users_to_project(
        self, lof_usernames: list[str], project_name: str
    ) -> list[UserEnrollment]:
        """Enroll multiple users to the project.

        :param lof_usernames: A list of usernames.
        :type lof_usernames: list[str]
        :param project_name: Project name.
        :type project_name: str
        :raises ProjectNotExistException: Project with the given name does not exist.
        :raises MaxUserCountReachedException: Project has already reached the maximum
            number of enrolled users.
        :raises PortUsageCollisionException: The port is already in use.
        :return: A list of generated user enrollments.
        :rtype: list[UserEnrollment]
        """
        # check project existence
        project = self._prj_mgr.get_project(project_name)

        nof_existing_users = len(self.get_user_enrollments_for_project_raw(project))
        new_users = self.filter_users_not_in_project(project, lof_usernames)
        if nof_existing_users + len(new_users) > project.max_nof_users:
            raise MaxUserCountReachedException(
                f"Project `{project.name}` has already reached the maximum number of users."
            )

        min_sshport = self.get_min_available_sshport(project)
        if min_sshport + len(new_users) - 1 > 65_535:
            raise SSHPortOutOfRangeException(
                "Not enough available ports."
            )  # pragma: no cover

        users = self._user_mgr.get_docs(username={"$in": new_users}, active=True)
        user_enrollments = []
        # TODO: collision_test
        for i, user in enumerate(users):
            user_enrollments.append(
                UserEnrollment(
                    user_id=DBRef("user", user.id),
                    project_id=DBRef("project", project.id),
                    container_port=min_sshport + i,
                    forwarded_port=min_sshport + i,
                    services={
                        "base": self.create_base_user_service(
                            user, project, min_sshport + i
                        )
                    },
                )
            )

        self._coll.insert_many([uc.model_dump() for uc in user_enrollments])
        return user_enrollments

    # LIST ENROLLMENTS

    def get_user_enrollments_for_project(
        self, project_or_name: "str | _project.Project", include_inactive: bool = False
    ) -> list[_user.User]:
        """Return list of users that are enrolled to the project.

        :param project_or_name: Project name or a `Project` object.
        :type project_or_name: str | Project
        :param include_inactive: Search for enrollments that are not active as well.
            Defaults to False.
        :type include_inactive: bool
        :raises ProjectNotExistException: Project data was not found in the database.
        :return: A list of enrolled users.
        :rtype: list[_user.User]
        """
        project = self._get_project(project_or_name)
        pipeline = MongoQueries.user_enrollment_get_enrolled_users(
            project, include_inactive
        )
        return [_user.User(**item) for item in self._coll.aggregate(pipeline)]

    def get_user_enrollments_for_project_raw(
        self, project_or_name: "str | _project.Project", include_inactive: bool = False
    ) -> list[dict]:
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
        :param include_inactive: Search for enrollments that are not active as well.
            Defaults to False.
        :type include_inactive: bool
        :raises ProjectNotExistException: Project data was not found in the database.
        :return: A list of raw results.
        :rtype: list[dict]
        """
        project = self._get_project(project_or_name)
        pipeline = MongoQueries.user_enrollment_get_enrolled_users_raw(
            project, include_inactive
        )
        return [
            {
                **item["users"],
                "mount": str(
                    (
                        self._paths["users"] / item["users"]["username"] / "home"
                    ).resolve()
                ),
                "forwarded_port": item["forwarded_port"],
            }
            for item in self.collection.aggregate(pipeline)
        ]

    def get_enrolled_projects(
        self, user_or_username: "str | _user.User", include_inactive: bool = False
    ) -> list["_project.Project"]:
        """Return list of projects that a user has enrolled to.

        :param username: User username.
        :type username: str
        :param include_inactive: Search for enrollments that are not active as well.
            Defaults to False.
        :type include_inactive: bool
        :raises UserNotExistsException: Given user could not be found in the database.
        :return: A list of enrolled projects for the given user.
        :rtype: list[_project.Project]
        """
        user = self._get_user(user_or_username)
        pipeline = MongoQueries.user_enrollment_get_enrolled_projects(
            user, include_inactive
        )
        return [_project.Project(**i) for i in self.collection.aggregate(pipeline)]

    def get_enrolled_projects_raw(
        self, user_or_username: "str | _user.User", include_inactive: bool = False
    ) -> list[RawEnrolledProjects]:
        """Return list of projects that a user has enrolled to.

        The output of the function is in raw format
        :param username: User username.
        :type username: str
        :param include_inactive: Search for enrollments that are not active as well.
            Defaults to False.
        :type include_inactive: bool
        :raises UserNotExistsException: Given user could not be found in the database.
        :return: A list of enrolled projects for the given user.
        :rtype: list[dict]
        """
        user = self._get_user(user_or_username)
        pipeline = MongoQueries.user_enrollment_get_enrolled_projects_raw(
            user, include_inactive
        )
        return [i for i in self.collection.aggregate(pipeline)]

    def get_all_enrolled_projects_raw(
        self, user_or_username: "str | _user.User"
    ) -> list[dict]:
        user = self._get_user(user_or_username)
        pipeline = MongoQueries.user_enrollment_get_all_enrolled_projects(user)
        return [i for i in self.collection.aggregate(pipeline)]

    # GET MODULE COUNT

    def get_modules_count(
        self, project_or_name: "str | _project.Project | None"
    ) -> list[ModuleCount]:
        _filter: dict = {"active": True}
        if project_or_name:
            project = self._get_project(project_or_name)
            _filter["project_id.$id"] = project.id

        pipeline = [{"$match": _filter}, *MongoQueries.count_module_name_occurences()]
        return [i for i in self.collection.aggregate(pipeline)]

    # CANCEL USER ENROLLMENTS

    def disable_enrollment(
        self,
        user_or_username: "str | _user.User",
        project_or_name: "str | _project.Project",
    ):
        user, project = self._get_user_and_project(user_or_username, project_or_name)

        user_enrollment = self.get_doc_by_filter(
            **{
                "user_id.$id": user.id,
                "project_id.$id": project.id,
                "active": True,
            }
        )

        if not user_enrollment:
            raise UserNotEnrolledToProjectException(
                f"User `{user.username}` is not enrolled to the project `{project.name}`"
            )

        self.stop_user_cluster(user, project)
        self.c_client.rm_networks(
            get_or_create_logger(project.name), f"{project.name}_{user.username}_"
        )

        user_enrollment.active = False
        self.update_doc(user_enrollment)

    def disable_multiple_enrollments(
        self, user_project_pairs: list[tuple[_user.User, "_project.Project"]]
    ):
        ue_ids = []
        for user, project in user_project_pairs:
            ue = self.get_doc_by_filter(
                **{"user_id.$id": user.id, "project_id.$id": project.id, "active": True}
            )
            if ue:
                self.c_client.compose_down(
                    get_or_create_logger(project.name),
                    self.get_compose_file(user, project),
                )
                self.c_client.rm_networks(
                    get_or_create_logger(project.name),
                    f"{project.name}_{user.username}_",
                )
                ue_ids.append(ue.id)
        self.collection.update_many(
            {"_id": {"$in": ue_ids}}, {"$set": {"active": False}}
        )

    def flush_enrollment(
        self,
        user_or_username: "str | _user.User",
        project_or_name: "str | _project.Project",
    ):
        user, project = self._get_user_and_project(user_or_username, project_or_name)

        user_enrollment = self.get_doc_by_filter(
            **{
                "user_id.$id": user.id,
                "project_id.$id": project.id,
            }
        )

        if not user_enrollment:
            return
        if user_enrollment.active:
            raise UserEnrolledToProjectException(
                "Cannot flush data when the enrollment is active."
            )

        # remove user_compose.yaml
        compose_path = (
            self._paths["projects"]
            / project.name
            / "users"
            / f"{user.username}_compose.yaml"
        )
        if compose_path.exists():
            compose_path.unlink()
        self.remove_doc_by_id(user_enrollment.id)

    def flush_multiple_enrollments(
        self, user_project_pairs: list[tuple["_user.User", "_project.Project"]]
    ):
        pipeline = MongoQueries.user_enrollment_aggregate_pairs_user_project(
            user_project_pairs
        )
        query_res = self.collection.aggregate(pipeline)
        for data in query_res:
            user = _user.User(**data["user"])
            project = _project.Project(**data["project"])
            compose_path = (
                self._paths["projects"]
                / project.name
                / "users"
                / f"{user.username}_compose.yaml"
            )
            if compose_path.exists():
                compose_path.unlink()

        self.remove_docs_by_id([data["_id"] for data in query_res])

    def cancel_user_enrollment(
        self,
        user_or_username: "str | _user.User",
        project_or_name: "str | _project.Project",
    ):
        """Cancel user enrollment.

        :param user_or_username: User username or user object.
        :type user_or_username: str | _user.User
        :param project_or_name: Project name or project object.
        :type project_or_name: str | _project.Project
        :raises UserNotExistsException: User with the given username was not found.
        :raises ProjectNotExistException: Project data was not found in the database.
        :raises UserNotEnrolledToProjectException: User is not enrolled to the given
        project.
        """
        self.disable_enrollment(user_or_username, project_or_name)
        # NOTE: flush the files as well?
        self.flush_enrollment(user_or_username, project_or_name)

    def cancel_multiple_enrollments(
        self, lof_usernames: list[str], project_or_name: "str | _project.Project"
    ):
        """Cancel multiple enrollment to a selected project.

        :param lof_usernames: A list of usernames.
        :type lof_usernames: list[str]
        :param project_or_name: Project name or project object.
        :type project_or_name: str | _project.Project
        :raises ProjectNotExistException: Project data was not found in the database.
        """
        project = self._get_project(project_or_name)
        pairs_user_project = [
            (user, project)
            for user in self._user_mgr.get_docs(
                username={"$in": lof_usernames}, active=True
            )
        ]
        self.disable_multiple_enrollments(pairs_user_project)
        self.flush_multiple_enrollments(pairs_user_project)

    def cancel_all_project_enrollments(self, project_or_name: "str | _project.Project"):
        """Remove all user enrollments for the given project.

        :param project_or_name: Project name or `Project` object.
        :type project_or_name: str | _project.Project
        :raises ProjectNotExistException: Project data was not found in the database.
        """
        project = self._get_project(project_or_name)
        pairs_user_project = [
            (user, project) for user in self.get_user_enrollments_for_project(project)
        ]
        self.disable_multiple_enrollments(pairs_user_project)
        self.flush_multiple_enrollments(pairs_user_project)

    def cancel_user_from_all_projects(self, user_or_username: "str | _user.User"):
        """Remove user from all enrolled projects.

        :param user_or_username: User username or `User` object.
        :type user_or_username: str | _user.User
        :raises UserNotExistsException: User with the given username was not found.
        """

        user = self._get_user(user_or_username)
        pairs_user_project = [
            (user, project) for project in self.get_enrolled_projects(user)
        ]
        self.disable_multiple_enrollments(pairs_user_project)
        self.flush_multiple_enrollments(pairs_user_project)

    def clear_database(self):
        """Remove all canceled user enrollments."""
        self.remove_docs_by_filter(active=False)

    # MANAGE SERVICES

    def register_service(
        self,
        user_or_username: "str | _user.User",
        project_or_name: "str | _project.Project",
        service_name: str,
        node_service: Service,
    ):
        user, project = self._get_user_and_project(user_or_username, project_or_name)
        try:
            ue = self.get_user_enrollment(user, project)
        except UserNotEnrolledToProjectException as e:
            raise UserNotEnrolledToProjectException(e)

        ue.register_node_service(service_name, node_service)
        self.update_doc(ue)

    def get_service(
        self,
        user_or_username: "str | _user.User",
        project_or_name: "str | _project.Project",
        service_name: str,
    ) -> Service:
        user, project = self._get_user_and_project(user_or_username, project_or_name)
        try:
            ue = self.get_user_enrollment(user, project)
        except UserNotEnrolledToProjectException as e:
            raise UserNotEnrolledToProjectException(e)

        return ue.get_node_service(service_name)

    def update_service(
        self,
        user_or_username: "str | _user.User",
        project_or_name: "str | _project.Project",
        service_name: str,
        node_service: Service,
    ):
        user, project = self._get_user_and_project(user_or_username, project_or_name)
        try:
            ue = self.get_user_enrollment(user, project)
        except UserNotEnrolledToProjectException as e:
            raise UserNotEnrolledToProjectException(e)

        ue.update_node_service(service_name, node_service)
        self.update_doc(ue)

    def list_services(
        self,
        user_or_username: "str | _user.User",
        project_or_name: "str | _project.Project",
    ) -> dict[str, Service]:
        user, project = self._get_user_and_project(user_or_username, project_or_name)
        try:
            ue = self.get_user_enrollment(user, project)
        except UserNotEnrolledToProjectException as e:
            raise UserNotEnrolledToProjectException(e)

        return ue.list_nodes_services()

    def remove_service(
        self,
        user_or_username: "str | _user.User",
        project_or_name: "str | _project.Project",
        service_name: str,
    ) -> Service | None:
        user, project = self._get_user_and_project(user_or_username, project_or_name)
        try:
            ue = self.get_user_enrollment(user, project)
        except UserNotEnrolledToProjectException as e:
            raise UserNotEnrolledToProjectException(e)

        service = ue.remove_node_service(service_name)
        self.update_doc(ue)
        return service

    # MANAGE CLUSTER

    def start_user_cluster(
        self,
        user_or_username: "str | _user.User",
        project_or_name: "str | _project.Project",
    ) -> int:
        """Start user cluster.

        :param user_or_username: User username or `User` object.
        :type user_or_username: str | _user.User
        :param project_or_name: Project name or `Project` object.
        :type project_or_name: str | _project.Project
        :raises UserNotExistsException: User with the given username was not found.
        :raises ProjectNotExistException: Project data was not found in the database.
        :raises UserNotEnrolledToProjectException: Given user is not enrolled to the
            project.
        :return: An exit code.
        :rtype: int
        """
        user, project = self._get_user_and_project(user_or_username, project_or_name)
        try:
            _ = self.get_user_enrollment(user, project)
        except UserNotEnrolledToProjectException as e:
            raise UserNotEnrolledToProjectException(e)
        compose_file = self.get_compose_file(user, project)

        return self.c_client.compose_up(
            get_or_create_logger(project.name), compose_file
        )

    def stop_user_cluster(
        self,
        user_or_username: "str | _user.User",
        project_or_name: "str | _project.Project",
    ) -> int:
        """Stop user cluster.

        :param user_or_username: User username or `User` object.
        :type user_or_username: str | _user.User
        :param project_or_name: Project name or `Project` object.
        :type project_or_name: str | _project.Project
        :raises UserNotExistsException: User with the given username was not found.
        :raises ProjectNotExistException: Project data was not found in the database.
        :raises ComposeFileNotExist: Compose file for the given user not found.
        :raises UserNotEnrolledToProjectException: Given user is not enrolled to the
            project.
        :return: An exit code.
        :rtype: int
        """
        user, project = self._get_user_and_project(user_or_username, project_or_name)
        try:
            _ = self.get_user_enrollment(user, project)
        except UserNotEnrolledToProjectException as e:
            raise UserNotEnrolledToProjectException(e)
        compose_file = self.get_compose_file(user, project)

        return self.c_client.compose_down(
            get_or_create_logger(project.name), compose_file
        )

    def user_cluster_is_running(
        self,
        user_or_username: "str | _user.User",
        project_or_name: "str | _project.Project",
    ) -> bool:
        """Check if user cluster is running.

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
        user, project = self._get_user_and_project(user_or_username, project_or_name)
        try:
            _ = self.get_user_enrollment(user, project)
        except UserNotEnrolledToProjectException as e:
            raise UserNotEnrolledToProjectException(e)
        compose_file = self.get_compose_file(user, project)
        return len(self.c_client.compose_ps(compose_file)) > 0

    def restart_user_cluster(
        self,
        user_or_username: "str | _user.User",
        project_or_name: "str | _project.Project",
    ):
        """Restart the user cluster.

        :param user_or_username: User username or `User` object.
        :type user_or_username: str | _user.User
        :param project_or_name: Project name or `Project` object.
        :type project_or_name: str | _project.Project
        :raises UserNotExistsException: User with the given username was not found.
        :raises ProjectNotExistException: Project data was not found in the database.
        :raises UserNotEnrolledToProjectException: Given user is not enrolled to the
            project.
        """
        user, project = self._get_user_and_project(user_or_username, project_or_name)
        try:
            _ = self.get_user_enrollment(user, project)
        except UserNotEnrolledToProjectException as e:
            raise UserNotEnrolledToProjectException(e)
        self.stop_user_cluster(user, project)
        self.start_user_cluster(user, project)

    def build_user_cluster_images(
        self,
        user_or_username: "str | _user.User",
        project_or_name: "str | _project.Project",
    ) -> int:
        """Build instances in the user cluster.

        :param user_or_username: User username or `User` object.
        :type user_or_username: str | _user.User
        :param project_or_name: Project name or `Project` object.
        :type project_or_name: str | _project.Project
        :raises UserNotExistsException: User with the given username was not found.
        :raises ProjectNotExistException: Project data was not found in the database.
        :raises UserNotEnrolledToProjectException: Given user is not enrolled to the
            project.
        :return: An exit code.
        :rtype: int
        """
        user, project = self._get_user_and_project(user_or_username, project_or_name)
        try:
            _ = self.get_user_enrollment(user, project)
        except UserNotEnrolledToProjectException as e:
            raise UserNotEnrolledToProjectException(e)
        compose_file = self.get_compose_file(user, project)
        return self.c_client.compose_build(
            get_or_create_logger(project.name), compose_file
        )

    def user_cluster_health_check(
        self,
        user_or_username: "str | _user.User",
        project_or_name: "str | _project.Project",
    ) -> list[HealthCheckDict]:
        user, project = self._get_user_and_project(user_or_username, project_or_name)
        try:
            _ = self.get_user_enrollment(user, project)
        except UserNotEnrolledToProjectException as e:
            raise UserNotEnrolledToProjectException(e)
        return self.c_client.compose_states(self.get_compose_file(user, project))

    def stop_multiple_user_clusters(
        self, users: list[_user.User], project: "_project.Project"
    ):
        """Stop multiple user clusters.

        :param users: A list of user object that should be linked with the project and its
            nodes will be stopped.
        :type users: list[_user.User]
        :param project: A project object.
        :type project: _project.Project
        """
        compose_files = []
        for user in users:
            try:
                compose_files.append(self.get_compose_file(user, project))
            except UserNotEnrolledToProjectException:
                pass

        for cfile in compose_files:
            self.c_client.compose_down(get_or_create_logger(project.name), cfile)

    def stop_all_user_clusters(self, project: "_project.Project"):
        """Stop all user clusters.

        :param project: A project object.
        :type project: _project.Project
        """
        lof_users = self.get_user_enrollments_for_project(project)

        compose_files = []
        for user in lof_users:
            try:
                compose_files.append(self.get_compose_file(user, project))
            except UserNotEnrolledToProjectException:
                pass

        for cfile in compose_files:
            self.c_client.compose_down(get_or_create_logger(project.name), cfile)
