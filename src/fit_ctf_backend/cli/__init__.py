import os
import pathlib
import sys

import click
import pymongo.errors

from fit_ctf_backend.cli.debug import debug
from fit_ctf_backend.ctf_manager import CTFManager
from fit_ctf_utils.constants import MODULE_SHARE_PATH, PRJ_SHARE_PATH, USER_SHARE_PATH
from fit_ctf_utils.types import PathDict

from . import completion, enrollment, module, project, user, user_cluster


def _get_db_info() -> tuple[str, str]:
    db_host = os.getenv("DB_HOST")
    if not db_host:
        sys.exit("Environment variable `DB_HOST` is not set.")

    db_name = os.getenv("DB_NAME")
    if not db_name:
        sys.exit("Environment variable `DB_NAME` is not set.")
    return db_host, db_name


@click.group("cli")
@click.option(
    "-pd",
    "--project-dir",
    type=click.Path(path_type=pathlib.Path),
    help="Directory that contains project folders.",
)
@click.option(
    "-ud",
    "--user-dir",
    type=click.Path(path_type=pathlib.Path),
    help="Directory that contains user folders.",
)
@click.option(
    "-md",
    "--module-dir",
    type=click.Path(path_type=pathlib.Path),
    help="Directory that contains module folders.",
)
@click.pass_context
def cli(
    ctx: click.Context,
    project_dir: pathlib.Path | None,
    user_dir: pathlib.Path | None,
    module_dir: pathlib.Path | None,
):
    """A tool for CTF competition management."""
    db_host, db_name = _get_db_info()
    paths = PathDict(
        **{
            "projects": project_dir if project_dir is not None else PRJ_SHARE_PATH,
            "users": user_dir if user_dir is not None else USER_SHARE_PATH,
            "modules": module_dir if module_dir is not None else MODULE_SHARE_PATH,
        }
    )

    try:
        ctf_mgr = CTFManager(db_host, db_name, paths)

        ctx.obj = {
            "db_host": db_host,
            "db_name": db_name,
            "ctf_mgr": ctf_mgr,
        }
    except pymongo.errors.ServerSelectionTimeoutError:
        click.echo(
            "Could not connect to the database. Make sure that the mongo database is running.\n"
            "Use the given script `./manage_db.sh` to manage the database.\n"
            "\n"
            "./manage_db.sh start - start the database.\n"
            "./manage_db.sh stop  - stop the database.\n"
            "./manage_db.sh       - print help"
        )
        exit(1)


cli.add_command(project.project)
cli.add_command(user.user)
cli.add_command(completion.completion)
cli.add_command(enrollment.enrollment)
cli.add_command(user_cluster.user_cluster)
cli.add_command(module.module)
cli.add_command(debug)
