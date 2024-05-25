import os

from jinja2 import Environment, FileSystemLoader, Template

TEMPLATE_DIRNAME = os.path.dirname(os.path.realpath(__file__))
TEMPLATE_FILES = {
    "shadow": "shadow.j2",
    "server_compose": "server_compose.yaml.j2",
    "user_compose": "user_compose.yaml.j2",
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
