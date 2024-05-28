from __future__ import annotations

import os
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, Template

TEMPLATE_DIRNAME = os.path.dirname(os.path.realpath(__file__))
TEMPLATE_FILES: dict[str, str] = {
    "shadow": "shadow.j2",
    "server_compose": "server_compose.yaml.j2",
    "user_compose": "user_compose.yaml.j2",
    "module_compose": "module_compose.yaml.j2",
}
TEMPLATE_PATHS: dict[str, Path] = {
    "project_module": Path(TEMPLATE_DIRNAME) / "module" / "project",
    "user_module": Path(TEMPLATE_DIRNAME) / "module" / "user",
}


def get_template(
    template_filename: str, template_dir: str = TEMPLATE_DIRNAME
) -> Template:
    """Return a Jinja template for rendering.

    Params:
        template_filename (str): A template's filename.
        template_dir (str, optional):
            A source directory that contains `template_filename`.
            Defaults to TEMPLATE_DIRNAME.

    Returns:
        Template: A retrieved template.
    """
    loader = FileSystemLoader(template_dir)
    env = Environment(loader=loader)

    return env.get_template(template_filename)
