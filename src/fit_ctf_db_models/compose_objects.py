from __future__ import annotations

from dataclasses import dataclass, field

from fit_ctf_backend.constants import DEFAULT_MODULE_BUILD_DIRNAME
from fit_ctf_templates import TEMPLATE_FILES


@dataclass
class Module(dict):
    """A module class that serves to define various services/nodes.

    :param name: Module name.
    :type name: str
    :param root_dir: Path to module configuration directory.
    :type root_dir: str
    :param build_dir_name: Path to a directory containing `Containerfile` used to build
        the container image. It should be inside <root_dir> directory.
    :type build_dir_name: str
    :param compose_template_path: Name of the Jinja2 template compose file.
    :type compose_template_path: str
    """

    name: str
    root_dir: str
    build_dir_name: str = field(default=DEFAULT_MODULE_BUILD_DIRNAME)
    compose_template_path: str = field(default=TEMPLATE_FILES["module_compose"])
