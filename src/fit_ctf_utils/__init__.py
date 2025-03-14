import logging
import os
import sys
import tempfile
from pathlib import Path
from subprocess import call

import yaml

from fit_ctf_utils.config_loader.yaml_parser import YamlParser
from fit_ctf_utils.container_client.container_client_interface import (
    ContainerClientInterface,
)
from fit_ctf_utils.container_client.docker_client import DockerClient
from fit_ctf_utils.container_client.mock_client import MockClient
from fit_ctf_utils.container_client.podman_client import PodmanClient
from fit_ctf_utils.exceptions import ConfigurationFileNotEditedException


def get_c_client_by_name(name: str) -> type[ContainerClientInterface]:
    """Choose the container client wrapper.

    :param name: A name of the container engine/
    :type name: str
    :raises ValueError: When unsupported container engine was given.
    :return: A `ContainerClientInterface` based class.
    :rtype: type[ContainerClientInterface]
    """
    if name == "podman":
        return PodmanClient
    elif name == "mock":
        return MockClient
    elif name == "docker":
        return DockerClient
    else:  # pragma: no cover
        raise ValueError("Given container engine name is not supported.")


logger_format = "[%(asctime)s] - %(levelname)s: %(message)s"


def get_or_create_logger(
    logger_name: str,
    is_file: bool = True,
    format: str | None = None,
    level=logging.INFO,
) -> logging.Logger:
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
        name: str,
        handler: logging.Handler,
        level=logging.INFO,
        format: str | None = None,
    ) -> logging.Logger:
        if format is None:
            handler.setFormatter(logging.Formatter(logger_format))
        else:
            handler.setFormatter(logging.Formatter(format))

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
        return setup_logger(logger_name, handler, level, format)
    return logging.getLogger(logger_name)


# NOTE: source link of the code: https://stackoverflow.com/a/6309753
def document_editor(doc: dict, read_only: set = set()) -> dict:
    """Allows user to edit configuration files in the system editor."""
    editor = os.getenv("EDITOR", "vim")
    excluded_data = {k: doc.pop(k) for k in read_only if k in doc}

    with tempfile.NamedTemporaryFile(suffix=".tmp", mode="w+") as tf:
        # dump the content of the data into the file
        yaml.dump(doc, tf, default_flow_style=True)
        tf.flush()

        initial_mod_time = os.path.getmtime(tf.name)

        # call the editor for editing
        call([editor, tf.name])

        # check if the file was modified
        if not (os.path.getmtime(tf.name) > initial_mod_time):
            raise ConfigurationFileNotEditedException()

        # do the parsing with `tf` using regular File operations.
        # for instance:
        tf.seek(0)
        doc = yaml.safe_load(tf)

    doc.update(excluded_data)
    return doc


# global logger writes to STDOUT
log = get_or_create_logger(__name__, False)
log_print = get_or_create_logger(f"{__name__}_print", False, "")

yamlParser = YamlParser()
