import pathlib

import click

from fit_ctf_backend.cli.utils import (
    format_option,
    project_option,
    yaml_suffix_validation,
)
from fit_ctf_backend.ctf_manager import CTFManager
from fit_ctf_utils.data_view import get_view
from fit_ctf_utils.exceptions import CTFException


@click.group(name="data-mgmt")
@click.pass_context
def data_mgmt(ctx: click.Context):
    ctx.obj = ctx.parent.obj  # pyright: ignore


@data_mgmt.command(name="export")
@project_option
@click.option(
    "-o",
    "--output-file",
    default="project_archive.zip",
    help="Final ZIP file name.",
    show_default=True,
)
@click.pass_context
def export_data(ctx: click.Context, project_name: str, output_file: str):
    """Export project data from the host machine.

    Generates a ZIP file containing all the project configuration files, including
    users and modules.
    """
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    try:
        ctf_mgr.export_project(project_name, output_file)
    except CTFException as e:
        click.echo(e)


@data_mgmt.command(name="import")
@click.option(
    "-i",
    "--input-file",
    required=True,
    type=click.Path(path_type=pathlib.Path, exists=True),
    help="The archive filepath.",
)
@click.pass_context
def import_data(ctx: click.Context, input_file: pathlib.Path):
    """Import project data from external machine.

    Loads the ZIP archive containing important data required for creating similar
    environment as the origin.
    """
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    try:
        ctf_mgr.import_project(input_file)
    except CTFException as e:
        click.echo(e)


@data_mgmt.command(name="setup")
@click.option(
    "-i",
    "--input-file",
    required=True,
    type=click.Path(path_type=pathlib.Path, exists=True),
    callback=yaml_suffix_validation,
    help="A path to the YAML configuration file.",
)
@click.option(
    "-E", "--exist-ok", is_flag=True, help="Ignore objects that already exist."
)
@click.option(
    "-D",
    "--dry-run",
    is_flag=True,
    help="Simulate running the setup without applying any changes.",
)
@format_option
@click.pass_context
def setup_data(
    ctx: click.Context,
    input_file: pathlib.Path,
    exist_ok: bool,
    dry_run: bool,
    format: str,
):
    """Setup environment from the YAML config file."""
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore

    try:
        new_users = ctf_mgr.setup_env_from_file(input_file, exist_ok, dry_run)
        if new_users:
            headers = ["Username", "Password"]
            values = [
                [user[label] for label in ["username", "password"]]
                for user in new_users
            ]
            get_view(format).print_data(headers, values)
    except CTFException as e:
        click.echo(e)
