import logging
import os
import sys
from pathlib import Path

from fit_ctf_utils.container_client.base_container_client import BaseContainerClient
from fit_ctf_utils.container_client.mock_client import MockClient
from fit_ctf_utils.container_client.podman_client import PodmanClient


def get_c_client_by_name(name: str) -> type[BaseContainerClient]:
    if name == "podman":
        return PodmanClient
    elif name == "mock":
        return MockClient
    else:  # pragma: no cover
        raise ValueError("Given container engine name is not supported.")


logger_format = "[%(asctime)s] - %(levelname)s: %(message)s"


def get_or_create_logger(logger_name: str, is_file: bool = True) -> logging.Logger:
    def setup_logger(
        name: str, handler: logging.Handler, level=logging.INFO
    ) -> logging.Logger:
        handler.setFormatter(logging.Formatter(logger_format))

        logger = logging.getLogger(name)
        logger.setLevel(level)
        logger.addHandler(handler)

        return logger

    # logger not defined
    if logger_name not in logging.Logger.manager.loggerDict.keys():
        # create handler based on the `is_file` condition
        handler = (
            logging.FileHandler(
                Path(os.getenv("LOG_DEST", "./")) / f"{logger_name}.log"
            )
            if is_file
            else logging.StreamHandler(sys.stdout)
        )
        return setup_logger(logger_name, handler)
    return logging.getLogger(logger_name)


GLOBAL_LOGGER = get_or_create_logger("global", False)
