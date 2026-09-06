"""ProjectCluster model and management for CTF platform."""

import pathlib
import shutil
from typing import TYPE_CHECKING, Self, cast, overload

from bson import DBRef
from pymongo.collection import Collection
from pymongo.database import Database

import fit_ctf.models.core.project as project_module
from fit_ctf.components.container_client.container_client_interface import (
    ContainerClientInterface,
)
from fit_ctf.components.logger.logger_interface import LoggerInterface
from fit_ctf.components.types import ErrorCode, HealthCheckDict, ProjectNetworkMap
from fit_ctf.models.infra.cluster_mgr_mixin import (
    BaseCluster,
    ClusterManagerMixin,
)
from fit_ctf.models.infra.config_models import ScenarioConfig
from fit_ctf.models.infra.constants import CLUSTER_LOGGER_NAME
from fit_ctf.models.utils.exceptions import (
    ProjectClusterExistException,
    ProjectClusterNotExistException,
    ProjectNotExistException,
    ScenarioConfigNotExistException,
)
from fit_ctf.models.utils.repository import EntityRepository
from fit_ctf.path_mgmt import PathManagement

if TYPE_CHECKING:
    import fit_ctf.models.core.project as project


class ProjectCluster(BaseCluster):
    """ProjectCluster model representing project-level deployed scenarios."""

    project_id: DBRef

    class Builder:
        """Builder for creating ProjectCluster instances."""

        def __init__(self, name: str, project: "project.Project"):
            """Initialize ProjectCluster builder.

            :param name: ProjectCluster name
            :type name: str
            :param project: Associated project
            :type project: project.Project
            """
            self._name = name
            self._project = project
            self._scenario_configs: dict[str, ScenarioConfig] = {}

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

        def build(self) -> "ProjectCluster":
            """Build and return ProjectCluster instance.

            :return: Constructed ProjectCluster
            :rtype: ProjectCluster
            """
            return ProjectCluster(
                name=self._name,
                project_id=DBRef("project", self._project.id),
                scenario_configs=self._scenario_configs,
                scenario_names=list(self._scenario_configs.keys()),
            )


class ProjectClusterManager(ClusterManagerMixin[ProjectCluster]):
    """Manager for project cluster operations and lifecycle."""

    def __init__(
        self,
        db: Database,
        coll: Collection,
        model_cls: type[ProjectCluster],
        repo: EntityRepository,
        c_client: ContainerClientInterface,
        paths: PathManagement,
        logger: LoggerInterface,
    ):
        """Initialize ProjectClusterManager.

        :param db: MongoDB database instance
        :type db: Database
        :param coll: MongoDB collection object
        :type coll: Collection
        :param model_cls: Model class for ProjectCluster
        :type model_cls: type[ProjectCluster]
        :param repo: Entity repository
        :type repo: EntityRepository
        :param c_client: Container client interface
        :type c_client: ContainerClientInterface
        :param paths: Path management instance
        :type paths: PathManagement
        :param logger: Logger interface
        :type logger: LoggerInterface
        """
        super().__init__(db, coll, model_cls, c_client, paths, logger)
        self._repo = repo

    def get_project(self, cluster: ProjectCluster) -> "project.Project":
        """Get project from cluster.

        :param cluster: ProjectCluster instance
        :type cluster: ProjectCluster
        :return: Project instance
        :rtype: project.Project
        :raises ProjectNotExistException: If project not found
        """
        project = self._repo.get_project_by_id(cluster.project_id.id)
        if not project:
            raise ProjectNotExistException(f"Project {str(cluster.project_id.id)} not found")
        return project

    @overload
    def get_cluster(self, cluster_name_or_project: "project.Project") -> ProjectCluster: ...

    @overload
    def get_cluster(self, cluster_name_or_project: str) -> ProjectCluster: ...

    def get_cluster(self, cluster_name_or_project: "str | project.Project") -> ProjectCluster:
        """Get cluster by name or project.

        :param cluster_name_or_project: ProjectCluster name or Project object
        :type cluster_name_or_project: str | project.Project
        :return: ProjectCluster instance
        :rtype: ProjectCluster
        :raises ProjectClusterNotExistException: If cluster not found
        """
        if isinstance(cluster_name_or_project, project_module.Project):
            cluster = self.get_doc_by_filter(**{"project_id.$id": cluster_name_or_project.id})
            if not cluster:
                raise ProjectClusterNotExistException(
                    f"ProjectCluster for project '{cluster_name_or_project.id}' not found."
                )
        else:
            cluster = self.get_doc_by_filter(name=cluster_name_or_project)
            if not cluster:
                raise ProjectClusterNotExistException(
                    f"ProjectCluster '{cluster_name_or_project}' not found."
                )
        return cluster

    def get_network_map(
        self, cluster_or_project: "ProjectCluster | project.Project"
    ) -> ProjectNetworkMap:
        """Get network mapping for project cluster.

        :param cluster_or_project: ProjectCluster or Project instance
        :type cluster_or_project: ProjectCluster | project.Project
        :return: Network map with shared and operational network names
        :rtype: ProjectNetworkMap
        """
        if isinstance(cluster_or_project, ProjectCluster):
            project = self.get_project(cluster_or_project)
        else:
            project = cluster_or_project
        return {
            "shared": f"{project.name}_shared_net",
            "operational": f"{project.name}_operational_net",
        }

    def _scenario_global_and_destination(
        self, cluster: ProjectCluster, scenario_name: str
    ) -> tuple[pathlib.Path, pathlib.Path]:
        project = self.get_project(cluster)
        src = self.paths.scenario_global / scenario_name
        dst = self.paths.project_scenarios(project) / scenario_name
        return src, dst

    def _network_map_for_scenario_compile(self, cluster: ProjectCluster) -> dict[str, str]:
        return cast(dict[str, str], dict(self.get_network_map(self.get_project(cluster))))

    def _volume_context_extras(
        self, cluster: ProjectCluster, compile_destination: pathlib.Path
    ) -> dict[str, str]:
        project = self.get_project(cluster)
        return {
            "project_scenario_dir": str(compile_destination.resolve()),
            "project_name": project.name,
        }

    def _compose_template_extras(self, cluster: ProjectCluster) -> dict[str, str]:
        project = self.get_project(cluster)
        return {"project_name": project.name}

    def get_scenario_compose_file(
        self, cluster: ProjectCluster, scenario_name: str
    ) -> pathlib.Path:
        """Get path to scenario compose template file.

        :param cluster: ProjectCluster instance
        :type cluster: ProjectCluster
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
        project = self.get_project(cluster)
        scenario_dir = self.paths.project_scenarios(project) / scenario_name
        return scenario_dir / "scenario_compose.yaml.j2"

    def get_compose_files(self, cluster: ProjectCluster) -> list[pathlib.Path]:
        """Get all compose files for cluster scenarios.

        :param cluster: ProjectCluster instance
        :type cluster: ProjectCluster
        :return: List of paths to compose files
        :rtype: list[pathlib.Path]
        """
        project = self.get_project(cluster)
        root_dir = self.paths.project_scenarios(project)
        return [
            root_dir / scenario_name / "scenario_compose.yaml"
            for scenario_name in cluster.scenario_names
        ]

    def create_cluster(self, cluster: ProjectCluster) -> ProjectCluster:
        """Create a new project cluster.

        :param cluster: ProjectCluster object to create
        :type cluster: ProjectCluster
        :return: The created cluster
        :rtype: ProjectCluster
        :raises ProjectClusterExistException: If cluster already exists
        :raises ProjectNotExistException: If project doesn't exist
        """
        # Validate project exists
        project = self._repo.get_project_by_id(cluster.project_id.id)
        if not project:
            raise ProjectNotExistException(f"Project {cluster.project_id.id} not found.")

        # Check if cluster already exists for this project
        existing_cluster = self.get_doc_by_filter(**{"project_id.$id": project.id})
        if existing_cluster:
            raise ProjectClusterExistException(
                f"ProjectCluster already exists for project {project.id}"
            )

        # Check if cluster name is unique
        c = self.get_doc_by_filter(name=cluster.name)
        if c:
            raise ProjectClusterExistException(f"ProjectCluster {c.name} already exists")

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

    async def delete_cluster(self, cluster_or_name: str | ProjectCluster):
        """Delete a cluster and clean up its resources.

        :param cluster_or_name: ProjectCluster object or cluster name
        :type cluster_or_name: str | ProjectCluster
        :raises ProjectClusterNotExistException: If cluster doesn't exist
        """
        if isinstance(cluster_or_name, str):
            cluster = self.get_cluster(cluster_or_name)
        else:
            if not self.get_doc_by_id(cluster_or_name.id):
                raise ProjectClusterNotExistException(f"ProjectCluster {cluster_or_name}")
            cluster = cluster_or_name

        await self.stop_cluster(cluster)
        self.remove_doc_by_id(cluster.id)

        # Clean up scenario directories
        project = self.get_project(cluster)
        project_scenarios_path = self.paths.project_scenarios(project)

        for scenario_name in cluster.scenario_names:
            scenario_dir = project_scenarios_path / scenario_name
            if scenario_dir.exists() and scenario_dir.is_dir():
                shutil.rmtree(scenario_dir)

    async def start_cluster(self, cluster: ProjectCluster, *, verbose: bool = False) -> ErrorCode:
        """Start a project cluster.

        :param cluster: ProjectCluster object
        :type cluster: ProjectCluster
        :param verbose: Stream compose engine output to the terminal as well as log files
        :type verbose: bool
        :return: An exit code
        :rtype: ErrorCode
        """
        project = self.get_project(cluster)

        # Check if already running before starting
        if await self.cluster_is_running(cluster):
            self.logger.info(
                f"project_cluster start skipped (already running) cluster={cluster.name} "
                f"project={project.name}",
                logger_name=CLUSTER_LOGGER_NAME,
            )
            return 0

        self.logger.info(
            f"project_cluster start cluster={cluster.name} project={project.name}",
            logger_name=CLUSTER_LOGGER_NAME,
        )
        error_code = await self.c_client.compose_up(
            project.name,
            self.get_compose_files(cluster),
            to_stdout=verbose,
        )
        self.logger.info(
            f"project_cluster start done cluster={cluster.name} project={project.name} "
            f"exit_code={error_code}",
            logger_name=CLUSTER_LOGGER_NAME,
        )
        return error_code

    async def stop_cluster(self, cluster: ProjectCluster, *, verbose: bool = False) -> ErrorCode:
        """Stop a project cluster.

        :param cluster: ProjectCluster object
        :type cluster: ProjectCluster
        :param verbose: Stream compose engine output to the terminal as well as log files
        :type verbose: bool
        :return: An exit code
        :rtype: ErrorCode
        """
        project = self.get_project(cluster)
        self.logger.info(
            f"project_cluster stop cluster={cluster.name} project={project.name}",
            logger_name=CLUSTER_LOGGER_NAME,
        )
        error_code, ran_teardown = await self.c_client.compose_down(
            project.name,
            self.get_compose_files(cluster),
            to_stdout=verbose,
        )
        self.logger.info(
            f"project_cluster stop done cluster={cluster.name} project={project.name} "
            f"exit_code={error_code} teardown={ran_teardown}",
            logger_name=CLUSTER_LOGGER_NAME,
        )
        return error_code

    async def cluster_is_running(self, cluster: ProjectCluster) -> bool:
        """Check if a project cluster is running.

        :param cluster: ProjectCluster object
        :type cluster: ProjectCluster
        :return: True if cluster is running
        :rtype: bool
        """
        return len(await self.c_client.compose_ps(self.get_compose_files(cluster))) > 0

    async def restart_cluster(self, cluster: ProjectCluster, *, verbose: bool = False) -> ErrorCode:
        """Restart a project cluster.

        :param cluster: ProjectCluster object
        :type cluster: ProjectCluster
        :param verbose: Stream compose engine output to the terminal as well as log files
        :type verbose: bool
        :return: An exit code
        :rtype: ErrorCode
        """
        project = self.get_project(cluster)
        self.logger.info(
            f"project_cluster restart cluster={cluster.name} project={project.name}",
            logger_name=CLUSTER_LOGGER_NAME,
        )
        stop_code = await self.stop_cluster(cluster, verbose=verbose)
        start_code = await self.start_cluster(cluster, verbose=verbose)
        self.logger.info(
            f"project_cluster restart done cluster={cluster.name} project={project.name} "
            f"stop_exit={stop_code} start_exit={start_code}",
            logger_name=CLUSTER_LOGGER_NAME,
        )
        return start_code

    async def cluster_health_check(self, cluster: ProjectCluster) -> list[HealthCheckDict]:
        """Get health check status for a project cluster.

        :param cluster: ProjectCluster object
        :type cluster: ProjectCluster
        :return: Health check data for all services in the cluster
        :rtype: list[HealthCheckDict]
        """
        return await self.c_client.compose_states(self.get_compose_files(cluster))

    async def build_cluster_images(
        self, cluster: ProjectCluster, *, verbose: bool = False
    ) -> ErrorCode:
        """Build/rebuild cluster images.

        :param cluster: ProjectCluster object
        :type cluster: ProjectCluster
        :param verbose: Stream build output to the terminal as well as log files
        :type verbose: bool
        :return: An exit code
        :rtype: ErrorCode
        """
        project = self.get_project(cluster)
        return await self.c_client.compose_build(
            project.name,
            self.get_compose_files(cluster),
            to_stdout=verbose,
        )

    async def compose_logs(
        self,
        cluster: ProjectCluster,
        *,
        tail: int = 500,
        service: str | None = None,
        to_stdout: bool = True,
    ) -> ErrorCode:
        """Fetch recent compose service logs (bounded tail)."""
        project = self.get_project(cluster)
        return await self.c_client.compose_logs(
            project.name,
            self.get_compose_files(cluster),
            tail=tail,
            service=service,
            to_stdout=to_stdout,
        )

    async def compose_logs_text(
        self,
        cluster: ProjectCluster,
        *,
        tail: int = 500,
        service: str | None = None,
    ) -> str:
        """Return recent compose service logs as text (bounded tail)."""
        return await self.c_client.compose_logs_text(
            self.get_compose_files(cluster), tail=tail, service=service
        )

    def shell_into_service(self, cluster: ProjectCluster, service: str, command: str = "bash"):
        """Shell into a cluster service.

        :param cluster: ProjectCluster object
        :type cluster: ProjectCluster
        :param service: Service name
        :type service: str
        :param command: Command to run (default: bash)
        :type command: str
        """
        self.c_client.compose_shell(self.get_compose_files(cluster), service, command)

    async def get_resource_usage(self, cluster: ProjectCluster) -> list[dict[str, str]]:
        """Get cluster resource usage statistics.

        :param cluster: ProjectCluster object
        :type cluster: ProjectCluster
        :return: List of resource usage statistics
        :rtype: list[dict[str, str]]
        """
        project = self.get_project(cluster)
        return await self.c_client.stats(project.name)

    async def get_ps_data(self, cluster: ProjectCluster) -> list[str]:
        """Get running containers for cluster.

        :param cluster: ProjectCluster object
        :type cluster: ProjectCluster
        :return: List of container info
        :rtype: list[str]
        """
        project = self.get_project(cluster)
        return await self.c_client.ps(project.name)

    async def get_all_services_info(self, cluster: ProjectCluster) -> list[dict]:
        """Get all services information for cluster.

        :param cluster: ProjectCluster object
        :type cluster: ProjectCluster
        :return: List of service information
        :rtype: list[dict]
        """
        project = self.get_project(cluster)
        return await self.c_client.project_stats(project.name)
