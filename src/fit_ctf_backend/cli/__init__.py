import pathlib

import click
import pymongo.errors

from fit_ctf_backend.cli.debug import debug
from fit_ctf_backend.ctf_manager import CTFManager
from fit_ctf_utils.constants import get_db_info, get_paths
from fit_ctf_utils.types import PathDict

from . import (
    completion,
    data_mgmt,
    enrollment,
    module,
    project,
    project_cluster,
    system,
    user,
    user_cluster,
)


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

    paths = PathDict(
        **{
            key: value
            for key, value in zip(["projects", "users", "modules"], get_paths())
        }
    )
    if project_dir:  # pragma: no cover
        paths["projects"] = project_dir
    if user_dir:  # pragma: no cover
        paths["users"] = user_dir
    if module_dir:  # pragma: no cover
        paths["modules"] = module_dir

    # system commands are offline commands that do not require database to be running
    # some commands like `start a database`, or `uninstall`
    # will be located in system group
    if ctx.invoked_subcommand == "system":  # pragma: no cover
        ctx.obj["paths"] = paths
        return

    db_host, db_name = get_db_info()
    try:
        ctf_mgr = CTFManager(db_host, db_name, paths)

        ctx.obj = {
            "db_host": db_host,
            "db_name": db_name,
            "ctf_mgr": ctf_mgr,
        }
    except pymongo.errors.ServerSelectionTimeoutError:  # pragma: no cover
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
cli.add_command(project_cluster.project_cluster)
cli.add_command(module.module)
cli.add_command(system.system)
cli.add_command(data_mgmt.data_mgmt)
cli.add_command(debug)
