from fit_ctf_utils.container_client.base_container_client import BaseContainerClient
from fit_ctf_utils.container_client.mock_client import MockClient
from fit_ctf_utils.container_client.podman_client import PodmanClient


def get_c_client_by_name(name: str) -> type[BaseContainerClient]:
    if name == "podman":
        return PodmanClient
    elif name == "mock":
        return MockClient
    else:
        raise ValueError("Given container engine name is not supported.")
