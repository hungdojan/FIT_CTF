from pydantic import BaseModel, Field

from fit_ctf_utils.exceptions import ServiceExistException, ServiceNotExistException


class Service(BaseModel):
    service_name: str
    module_name: str
    is_local: bool = True
    ports: list[str] = Field(default_factory=list)
    networks: dict = Field(default_factory=dict)
    volumes: list[str] = Field(default_factory=list)
    env: list[str] = Field(default_factory=list)
    other: dict = Field(default_factory=dict)


class ClusterConfig(BaseModel):
    services: dict[str, Service] = Field(default_factory=dict)
    networks: dict[str, dict] = Field(default_factory=dict)

    def register_node_service(
        self,
        service_name: str,
        node_service: Service,
    ):
        """Register a new service to a cluster.

        :param service_name: Name of the service.
        :type service_name: str
        :param node_service: The content of the service.
        :type node_service: Service
        :raises ServiceExistException:
            When the cluster already has a service with the given name.
        """
        if self.services.get(service_name):
            raise ServiceExistException(f"Service `{service_name}` already exist.")
        self.services[service_name] = node_service

    def get_node_service(self, service_name: str) -> Service:
        """Retrieve a service configuration data from the cluster.

        :param service_name: Name of the service.
        :type service_name: str
        :raises ServiceNotExistException:
            When the service with the given name could not be located.
        :return: Found service.
        :rtype: Service.
        """
        service = self.services.get(service_name)
        if not service:
            raise ServiceNotExistException(f"Service `{service_name}` was not found.")
        return service

    def update_node_service(self, service_name: str, node_service: Service):
        """Retrieve a service configuration data from the cluster.

        :param service_name: Name of the service.
        :type service_name: str
        :raises ServiceNotExistException:
            When the service with the given name could not be located.
        :param node_service: The content of the service.
        :type node_service: Service
        """
        if not self.services.get(service_name):
            raise ServiceNotExistException(f"Service `{service_name}` was not found.")
        self.services[service_name] = node_service

    def remove_node_service(self, service_name: str) -> Service | None:
        """Remove a service from the cluster if exists.

        :param service_name: Name of the service.
        :type service_name: str
        :return: A service if found; None otherwise.
        :rtype: Service | None
        """
        return self.services.pop(service_name, None)

    def list_nodes_services(self) -> dict[str, Service]:
        """Return a list of services in the cluster.

        :return: A dictionary containing services mapped to service names.
        :rtype: dict[str, Service]
        """
        return self.services
