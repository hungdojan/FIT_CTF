import logging
import os
import sys
from pathlib import Path

from fit_ctf_utils.container_client.base_container_client import BaseContainerClient
from fit_ctf_utils.container_client.mock_client import MockClient
from fit_ctf_utils.container_client.podman_client import PodmanClient


def get_c_client_by_name(name: str) -> type[BaseContainerClient]:
    """Choose the container client wrapper.

    :param name: A name of the container engine/
    :type name: str
    :raises ValueError: When unsupported container engine was given.
    :return: A `BaseContainerClient` based class.
    :rtype: type[BaseContainerClient]
    """
    if name == "podman":
        return PodmanClient
    elif name == "mock":
        return MockClient
    else:  # pragma: no cover
        raise ValueError("Given container engine name is not supported.")


logger_format = "[%(asctime)s] - %(levelname)s: %(message)s"


def get_or_create_logger(logger_name: str, is_file: bool = True) -> logging.Logger:
    """Get an existing or create a new logger.

    :param logger_name: Identification name of the logger.
    :type logger_name: str
    :param is_file: This flag is only meant to be used if the logger does not exist.
        If set to `True` the new logger will write to a file; otherwise to STDOUT,
        defaults to True.
    :type is_file: bool, optional
    :return: Found or a new logger.
    :rtype: logging.Logger
    """

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


# global logger writes to STDOUT
GLOBAL_LOGGER = get_or_create_logger("global", False)
