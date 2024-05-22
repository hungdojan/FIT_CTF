from pathlib import Path

import click
from bson import ObjectId

import fit_ctf_backend.cli as _cli
from fit_ctf_backend.ctf_manager import CTFManager
from fit_ctf_backend.demo import demo_project
from fit_ctf_db_models.project import Project
from fit_ctf_db_models.user import User
from fit_ctf_db_models.user_config import UserConfig
from fit_ctf_templates import TEMPLATE_DIRNAME, TEMPLATE_FILES, get_template

#########################
## Testing CLI command ##
#########################


@click.command(name="testing", help="A command used for testing purposes.")
def testing():
    """A command that manages users."""
    db_host, db_name = _cli._get_db_info()
    ctf_mgr = CTFManager(db_host, db_name)

    # demo_project(db_host, db_name)
    path = Path(TEMPLATE_DIRNAME) / "server_project"
    template = get_template("user_compose.yaml.j2", str(path))
    prj = ctf_mgr.get_project_info("demo")
    user = ctf_mgr.user_mgr.get_doc_by_filter(username="test2")
    user_config = ctf_mgr.user_config_mgr.get_doc_by_filter(
        _id=ObjectId("661668b043f399218db70244")
    )
    click.echo(template.render(project=prj, user=user, user_config=user_config))
