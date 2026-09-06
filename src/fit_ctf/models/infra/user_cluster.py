"""UserCluster model and management for CTF platform."""

import pathlib
import shutil
from typing import TYPE_CHECKING, Any, Self, cast, overload

from bson import DBRef, ObjectId
from pymongo.collection import Collection
from pymongo.database import Database

import fit_ctf.models.core.enrollment as enroll
from fit_ctf.components.container_client.container_client_interface import (
    ContainerClientInterface,
)
from fit_ctf.components.logger.logger_interface import LoggerInterface
from fit_ctf.components.types import ErrorCode, HealthCheckDict, UserNetworkMap
from fit_ctf.models.infra.cluster_mgr_mixin import BaseCluster, ClusterManagerMixin
from fit_ctf.models.infra.config_models import (
    ScenarioConfig,
    ServiceConfig,
    VolumeConfig,
)
from fit_ctf.models.infra.constants import CLUSTER_LOGGER_NAME
from fit_ctf.models.utils.exceptions import (
    ProjectClusterNotExistException,
    ScenarioConfigNotExistException,
    UserClusterExistException,
    UserClusterNotExistException,
    UserNotEnrolledToProjectException,
)
from fit_ctf.models.utils.repository import EntityRepository
from fit_ctf.models.utils.sessions import ProgressSession
from fit_ctf.path_mgmt import PathManagement

if TYPE_CHECKING:
    import fit_ctf.models.core.project as project
    import fit_ctf.models.core.user as user
    import fit_ctf.models.infra.project_cluster as project_cluster


class UserCluster(BaseCluster):
    enrollment_id: DBRef

    class Builder:
        """Builder for creating UserCluster instances."""

        def __init__(self, name: str, enrollment: "enroll.Enrollment"):
            """Initialize UserCluster builder.

            :param name: UserCluster name
            :type name: str
            :param enrollment: Associated enrollment
            :type enrollment: enroll.Enrollment
            """
            self._name = name
            self._enrollment = enrollment
            self._scenario_configs: dict[str, ScenarioConfig] = {}

        @staticmethod
        def generate_cluster_name(
            project: "project.Project",
            user: "user.User",
        ):
            return f"{project.name}_{user.username}"

        def add_scenario_config(self, scenario_name: str, scenario_config: ScenarioConfig) -> Self:
            """Add scenario configuration to cluster.

            :param scenario_name: Name of the scenario
            :type scenario_name: str
            :param scenario_config: Scenario configuration
            :type scenario_config: ScenarioConfig
            :return: Builder instance for chaining
            :rtype: Self
            """
            self._scenario_configs[scenario_name] = scenario_config
            return self

        def build(self) -> "UserCluster":
            """Build and return UserCluster instance.

            :return: Constructed UserCluster
            :rtype: UserCluster
            """
            return UserCluster(
                name=self._name,
                enrollment_id=DBRef("enrollment", self._enrollment.id),
                scenario_configs=self._scenario_configs,
                scenario_names=list(self._scenario_configs.keys()),
            )


class UserClusterManager(ClusterManagerMixin[UserCluster]):
    """Manager for cluster operations and lifecycle."""

    def __init__(
        self,
        db: Database,
        coll: Collection,
        model_cls: type[UserCluster],
        repo: EntityRepository,
        project_cluster_mgr: "project_cluster.ProjectClusterManager",
        c_client: ContainerClientInterface,
        paths: PathManagement,
        logger: LoggerInterface,
    ):
        """Initialize UserClusterManager.

        :param db: MongoDB database instance
        :type db: Database
        :param coll: MongoDB collection object
        :type coll: Collection
        :param model_cls: Model class for UserCluster
        :type model_cls: type[UserCluster]
        :param repo: Entity repository
        :type repo: EntityRepository
        :param project_cluster_mgr: Project cluster manager instance
        :type project_cluster_mgr: ProjectClusterManager
        :param c_client: Container client interface
        :type c_client: ContainerClientInterface
        :param paths: Path management instance
        :type paths: PathManagement
        :param logger: Logger interface
        :type logger: LoggerInterface
        """
        super().__init__(db, coll, model_cls, c_client, paths, logger)
        self._repo = repo
        self._project_cluster_mgr = project_cluster_mgr

    @staticmethod
    def create_base_user_cluster(
        project: "project.Project",
        user: "user.User",
        enrollment: "enroll.Enrollment",
        login_node_type: str | None = None,
    ) -> UserCluster:
        return (
            UserCluster.Builder(
                UserCluster.Builder.generate_cluster_name(project, user), enrollment
            )
            .add_scenario_config(
                "login_node",
                ScenarioConfig.Builder("login_node")
                .add_config_param("login_node_module", login_node_type or "ssh_ubi")
                .add_service(
                    "login_node",
                    ServiceConfig.Builder()
                    .add_volume(
                        "home",
                        VolumeConfig(
                            src_path="{{ paths__users }}/{{ username }}/home/",
                            template_params={},
                        ),
                    )
                    .add_volume(
                        "shadow",
                        VolumeConfig(
                            src_path="{{ paths__users }}/{{ username }}/shadow",
                            template_params={},
                        ),
                    )
                    .build(),
                )
                .build(),
            )
            .build()
        )

    def get_user_and_project(self, enrollment_id: ObjectId) -> "tuple[user.User, project.Project]":
        """Get user and project from enrollment ID.

        :param enrollment_id: Enrollment object ID
        :type enrollment_id: ObjectId
        :return: Tuple of (User, Project)
        :rtype: tuple[user.User, project.Project]
        :raises EnrollmentNotExistException: If enrollment not found
        :raises UserNotExistsException: If user not found
        :raises ProjectNotExistException: If project not found
        """
        enrollment = self._repo.get_enrollment_by_id(enrollment_id)
        user = self._repo.get_user_by_id(enrollment.user_id.id)
        project = self._repo.get_project_by_id(enrollment.project_id.id)
        return user, project

    @overload
    def get_cluster(self, cluster_name_or_enrollment: "enroll.Enrollment") -> UserCluster: ...

    @overload
    def get_cluster(self, cluster_name_or_enrollment: str) -> UserCluster: ...

    def get_cluster(self, cluster_name_or_enrollment: "str | enroll.Enrollment") -> UserCluster:
        """Get cluster by name or enrollment.

        :param cluster_name_or_enrollment: UserCluster name or Enrollment object
        :type cluster_name_or_enrollment: str | enroll.Enrollment
        :return: UserCluster instance
        :rtype: UserCluster
        :raises UserClusterNotExistException: If cluster not found
        """
        if isinstance(cluster_name_or_enrollment, enroll.Enrollment):
            cluster = self.get_doc_by_filter(**{"enrollment_id.$id": cluster_name_or_enrollment.id})
            if not cluster:
                raise UserClusterNotExistException(
                    f"UserCluster from enrollment '{cluster_name_or_enrollment.id}' not found."
                )
        else:
            cluster = self.get_doc_by_filter(name=cluster_name_or_enrollment)
            if not cluster:
                raise UserClusterNotExistException(
                    f"UserCluster '{cluster_name_or_enrollment}' not found."
                )
        return cluster

    @overload
    def get_network_map(self, cluster_or_project_user: UserCluster) -> UserNetworkMap: ...

    @overload
    def get_network_map(
        self, cluster_or_project_user: tuple["user.User", "project.Project"]
    ) -> UserNetworkMap: ...

    def get_network_map(
        self,
        cluster_or_project_user: UserCluster | tuple["user.User", "project.Project"],
    ) -> UserNetworkMap:
        """Get network mapping for cluster.

        :param cluster_or_project_user: UserCluster or tuple of (User, Project)
        :type cluster_or_project_user: UserCluster | tuple[user.User, project.Project]
        :return: Network map with shared and private network names
        :rtype: NetworkMap
        """
        if isinstance(cluster_or_project_user, UserCluster):
            user, project = self.get_user_and_project(cluster_or_project_user.enrollment_id.id)
        else:
            user, project = cluster_or_project_user
        return {
            "shared": f"{project.name}_shared_net",
            "private": f"{project.name}_{user.username}_private_net",
        }

    def _scenario_global_and_destination(
        self, cluster: UserCluster, scenario_name: str
    ) -> tuple[pathlib.Path, pathlib.Path]:
        user, project = self.get_user_and_project(cluster.enrollment_id.id)
        src = self.paths.scenario_global / scenario_name
        dst = self.paths.enrolled_user_path(user, project) / scenario_name
        return src, dst

    def _network_map_for_scenario_compile(self, cluster: UserCluster) -> dict[str, str]:
        user, project = self.get_user_and_project(cluster.enrollment_id.id)
        return cast(dict[str, str], dict(self.get_network_map((user, project))))

    def _enrollment_for_cluster(self, cluster: UserCluster) -> "enroll.Enrollment":
        return self._repo.get_enrollment_by_id(cluster.enrollment_id.id)

    def _volume_context_extras(
        self, cluster: UserCluster, compile_destination: pathlib.Path
    ) -> dict[str, Any]:
        user, project = self.get_user_and_project(cluster.enrollment_id.id)
        enrollment = self._enrollment_for_cluster(cluster)
        return {
            "user_scenario_dir": str(compile_destination.resolve()),
            "project_name": project.name,
            "username": user.username,
            "container_port": enrollment.container_port,
            "forwarded_port": enrollment.forwarded_port,
        }

    def _compose_template_extras(self, cluster: UserCluster) -> dict[str, Any]:
        user, project = self.get_user_and_project(cluster.enrollment_id.id)
        enrollment = self._enrollment_for_cluster(cluster)
        extras = {
            "project_name": project.name,
            "username": user.username,
            "container_port": enrollment.container_port,
            "forwarded_port": enrollment.forwarded_port,
        }
        # Add login_node_module with default value for login_node scenario
        if "login_node" in cluster.scenario_configs:
            login_node_cfg = cluster.scenario_configs["login_node"]
            extras["login_node_module"] = login_node_cfg.config_params.get(
                "login_node_module", "ssh_ubi"
            )
        return extras

    def get_scenario_compose_file(self, cluster: UserCluster, scenario_name: str) -> pathlib.Path:
        """Get path to scenario compose template file.

        :param cluster: UserCluster instance
        :type cluster: UserCluster
        :param scenario_name: Name of the scenario
        :type scenario_name: str
        :return: Path to compose template file
        :rtype: pathlib.Path
        :raises ScenarioConfigNotExistException: If scenario not in cluster
        """
        if scenario_name not in cluster.scenario_names:
            raise ScenarioConfigNotExistException(
                f"Scenario {scenario_name} is not used in {cluster.name}"
            )
        user, project = self.get_user_and_project(cluster.enrollment_id.id)
        scenario_dir = self.paths.enrolled_user_path(user, project) / scenario_name
        return scenario_dir / "scenario_compose.yaml.j2"

    def get_compose_files(self, cluster: UserCluster) -> list[pathlib.Path]:
        """Get all compose files for cluster scenarios.

        :param cluster: UserCluster instance
        :type cluster: UserCluster
        :return: List of paths to compose files
        :rtype: list[pathlib.Path]
        :raises FileNotFoundError: If enrollment path doesn't exist
        """
        user, project = self.get_user_and_project(cluster.enrollment_id.id)
        root_dir = self.paths.enrolled_user_path(user, project)
        if not root_dir.exists():
            raise FileNotFoundError(f"Enrolled user path does not exist: {root_dir}")
        return [
            root_dir / scenario_name / "scenario_compose.yaml"
            for scenario_name in cluster.scenario_names
        ]

    def create_cluster(self, cluster: UserCluster) -> UserCluster:
        """Create a new cluster.

        :param cluster: UserCluster object to create
        :type cluster: UserCluster
        :return: The created cluster
        :rtype: UserCluster
        :raises UserClusterExistException: If cluster with same name already exists
        :raises EnrollmentNotExistException: If enrollment doesn't exist
        """
        # Validate enrollment exists
        enrollment = self._repo.get_enrollment_by_id(cluster.enrollment_id.id)

        # Check if cluster already exists for this enrollment
        existing_cluster = self.get_doc_by_filter(**{"enrollment_id.$id": enrollment.id})
        if existing_cluster:
            raise UserClusterExistException(
                f"UserCluster already exists for enrollment {enrollment.id}"
            )

        # Check if cluster name is unique
        c = self.get_doc_by_filter(name=cluster.name)
        if c:
            raise UserClusterExistException(f"UserCluster {c.name} already exists")

        # Insert cluster document
        self.insert_doc(cluster)

        # Compile scenarios with rollback on failure
        try:
            for scenario_name in cluster.scenario_configs.keys():
                self.compile_scenario(cluster, scenario_name)
        except Exception as e:
            # Rollback: remove cluster document if scenario compilation fails
            self.remove_doc_by_id(cluster.id)
            raise e

        return cluster

    async def delete_cluster(
        self, cluster_or_name: str | UserCluster, enroll_mgr: "enroll.EnrollmentManager"
    ):
        """Delete a cluster and clean up its resources.

        :param cluster_or_name: UserCluster object or cluster name
        :type cluster_or_name: str | UserCluster
        :param enroll_mgr: Enrollment manager
        :type enroll_mgr: EnrollmentManager
        :raises UserClusterNotExistException: If cluster doesn't exist
        """
        if isinstance(cluster_or_name, str):
            cluster = self.get_cluster(cluster_or_name)
        else:
            if not self.get_doc_by_id(cluster_or_name.id):
                raise UserClusterNotExistException(f"UserCluster {cluster_or_name}")
            cluster = cluster_or_name

        try:
            await self.stop_cluster(cluster, enroll_mgr)
        except FileNotFoundError:
            pass
        self.remove_doc_by_id(cluster.id)

        # Clean up scenario directories only (not entire enrollment path)
        user, project = self.get_user_and_project(cluster.enrollment_id.id)
        enrollment_path = self.paths.enrolled_user_path(user, project)

        for scenario_name in cluster.scenario_names:
            scenario_dir = enrollment_path / scenario_name
            if scenario_dir.exists() and scenario_dir.is_dir():
                shutil.rmtree(scenario_dir)

    async def start_cluster(
        self,
        cluster: UserCluster,
        enroll_mgr: "enroll.EnrollmentManager",
        *,
        verbose: bool = False,
    ) -> ErrorCode:
        """Start a cluster.

        :param cluster: UserCluster object
        :type cluster: UserCluster
        :param enroll_mgr: Enrollment manager
        :type enroll_mgr: EnrollmentManager
        :param verbose: Stream compose engine output to the terminal as well as log files
        :type verbose: bool
        :return: An exit code
        :rtype: ErrorCode
        """
        user, project = self.get_user_and_project(cluster.enrollment_id.id)

        # Ensure project cluster is running first
        try:
            project_cluster = self._project_cluster_mgr.get_cluster(project)
            if not await self._project_cluster_mgr.cluster_is_running(project_cluster):
                await self._project_cluster_mgr.start_cluster(project_cluster, verbose=verbose)
        except ProjectClusterNotExistException:
            self.logger.debug(
                f"No project cluster for project={project.name}; skipping dependency start",
                logger_name=CLUSTER_LOGGER_NAME,
            )
        except Exception as e:
            self.logger.warning(
                f"Could not ensure project cluster is running for project={project.name}: {e}",
                logger_name=CLUSTER_LOGGER_NAME,
            )

        self.logger.info(
            f"user_cluster start cluster={cluster.name} user={user.username} "
            f"project={project.name}",
            logger_name=CLUSTER_LOGGER_NAME,
        )
        enrollment = self._repo.get_enrollment(user, project)
        enroll_mgr.record_session(enrollment, ProgressSession.State.START)
        error_code = await self.c_client.compose_up(
            project.name,
            self.get_compose_files(cluster),
            to_stdout=verbose,
        )
        self.logger.info(
            f"user_cluster start done cluster={cluster.name} user={user.username} "
            f"project={project.name} exit_code={error_code}",
            logger_name=CLUSTER_LOGGER_NAME,
        )
        return error_code

    async def stop_cluster(
        self,
        cluster: UserCluster,
        enroll_mgr: "enroll.EnrollmentManager",
        *,
        verbose: bool = False,
    ) -> ErrorCode:
        """Stop a cluster.

        :param cluster: UserCluster object
        :type cluster: UserCluster
        :param enroll_mgr: Enrollment manager
        :type enroll_mgr: EnrollmentManager
        :param verbose: Stream compose engine output to the terminal as well as log files
        :type verbose: bool
        :return: An exit code
        :rtype: ErrorCode
        """
        user, project = self.get_user_and_project(cluster.enrollment_id.id)
        self.logger.info(
            f"user_cluster stop cluster={cluster.name} user={user.username} project={project.name}",
            logger_name=CLUSTER_LOGGER_NAME,
        )
        enrollment = self._repo.get_enrollment(user, project, active=None)
        error_code, success = await self.c_client.compose_down(
            project.name,
            self.get_compose_files(cluster),
            to_stdout=verbose,
        )
        if success:
            enroll_mgr.record_session(enrollment, ProgressSession.State.STOP)
        self.logger.info(
            f"user_cluster stop done cluster={cluster.name} user={user.username} "
            f"project={project.name} exit_code={error_code} teardown={success}",
            logger_name=CLUSTER_LOGGER_NAME,
        )
        return error_code

    async def cluster_is_running(self, cluster: UserCluster) -> bool:
        """Check if a cluster is running.

        :param cluster: UserCluster object
        :type cluster: UserCluster
        :return: True if cluster is running
        :rtype: bool
        """
        return len(await self.c_client.compose_ps(self.get_compose_files(cluster))) > 0

    async def restart_cluster(
        self,
        cluster: UserCluster,
        enroll_mgr: "enroll.EnrollmentManager",
        *,
        verbose: bool = False,
    ) -> ErrorCode:
        """Restart a cluster.

        :param cluster: UserCluster object
        :type cluster: UserCluster
        :param enroll_mgr: Enrollment manager
        :type enroll_mgr: EnrollmentManager
        :param verbose: Stream compose engine output to the terminal as well as log files
        :type verbose: bool
        :return: An exit code
        :rtype: ErrorCode
        """
        user, project = self.get_user_and_project(cluster.enrollment_id.id)
        self.logger.info(
            f"user_cluster restart cluster={cluster.name} user={user.username} "
            f"project={project.name}",
            logger_name=CLUSTER_LOGGER_NAME,
        )
        stop_code = await self.stop_cluster(cluster, enroll_mgr, verbose=verbose)
        start_code = await self.start_cluster(cluster, enroll_mgr, verbose=verbose)
        self.logger.info(
            f"user_cluster restart done cluster={cluster.name} user={user.username} "
            f"project={project.name} stop_exit={stop_code} start_exit={start_code}",
            logger_name=CLUSTER_LOGGER_NAME,
        )
        return start_code

    async def compose_logs(
        self,
        cluster: UserCluster,
        *,
        tail: int = 500,
        service: str | None = None,
        to_stdout: bool = True,
    ) -> ErrorCode:
        """Fetch recent compose service logs (bounded tail)."""
        _, project = self.get_user_and_project(cluster.enrollment_id.id)
        return await self.c_client.compose_logs(
            project.name,
            self.get_compose_files(cluster),
            tail=tail,
            service=service,
            to_stdout=to_stdout,
        )

    async def compose_logs_text(
        self,
        cluster: UserCluster,
        *,
        tail: int = 500,
        service: str | None = None,
    ) -> str:
        """Return recent compose service logs as text (bounded tail)."""
        return await self.c_client.compose_logs_text(
            self.get_compose_files(cluster), tail=tail, service=service
        )

    async def cluster_health_check(self, cluster: UserCluster) -> list[HealthCheckDict]:
        """Get health check status for a cluster.

        :param cluster: UserCluster object
        :type cluster: UserCluster
        :return: Health check data for all services in the cluster
        :rtype: list[HealthCheckDict]
        """
        return await self.c_client.compose_states(self.get_compose_files(cluster))

    async def build_cluster_images(
        self, cluster: UserCluster, *, verbose: bool = False
    ) -> ErrorCode:
        """Build/rebuild cluster images.

        :param cluster: UserCluster object
        :type cluster: UserCluster
        :param verbose: Stream build output to the terminal as well as log files
        :type verbose: bool
        :return: An exit code
        :rtype: ErrorCode
        """
        _, project = self.get_user_and_project(cluster.enrollment_id.id)
        return await self.c_client.compose_build(
            project.name,
            self.get_compose_files(cluster),
            to_stdout=verbose,
        )

    async def stop_multiple_user_clusters(
        self,
        users: list["user.User"],
        project: "project.Project",
        enroll_mgr: "enroll.EnrollmentManager",
    ):
        """Stop multiple user clusters.

        :param users: List of user objects
        :type users: list[user.User]
        :param project: Project object
        :type project: project.Project
        :param enroll_mgr: Enrollment manager
        :type enroll_mgr: EnrollmentManager
        """
        for u in users:
            try:
                enrollment = self._repo.get_enrollment(u, project, active=None)
                cluster = self.get_doc_by_filter(**{"enrollment_id.$id": enrollment.id})
                if cluster:
                    await self.stop_cluster(cluster, enroll_mgr)
            except UserNotEnrolledToProjectException:
                pass

    async def stop_all_user_clusters(
        self, project: "project.Project", enroll_mgr: "enroll.EnrollmentManager"
    ):
        """Stop all user clusters in the project.

        :param project: Project object
        :type project: project.Project
        :param enroll_mgr: Enrollment manager
        :type enroll_mgr: EnrollmentManager
        """
        users = enroll_mgr.get_enrollments_for_project(project)
        await self.stop_multiple_user_clusters(users, project, enroll_mgr)

    async def stop_all_clusters_of_a_user(
        self, user: "user.User", enroll_mgr: "enroll.EnrollmentManager"
    ):
        """Stop all running clusters of a user.

        :param user: User object
        :type user: user.User
        :param enroll_mgr: Enrollment manager
        :type enroll_mgr: EnrollmentManager
        """
        projects = enroll_mgr.get_enrolled_projects(user)
        for p in projects:
            await self.stop_multiple_user_clusters([user], p, enroll_mgr)
