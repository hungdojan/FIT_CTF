import click

from fit_ctf_backend.cli.utils import format_option, module_name_option
from fit_ctf_backend.ctf_manager import CTFManager
from fit_ctf_utils.data_view import get_view
from fit_ctf_utils.exceptions import (
    ModuleExistsException,
    ModuleInUseException,
    ModuleNotExistsException,
)


@click.group(name="module")
@click.pass_context
def module(ctx: click.Context):
    """Manage local modules."""
    ctx.obj = ctx.parent.obj  # pyright: ignore


@module.command(name="create")
@module_name_option
@click.pass_context
def create(ctx: click.Context, module_name: str):
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    try:
        ctf_mgr.module_mgr.create_module(module_name)
    except ModuleExistsException as e:
        click.echo(e)
        exit(1)

    click.echo(f"Module `{module_name}` successfully created.")


@module.command(name="ls")
@format_option
@click.pass_context
def lists(ctx: click.Context, format: str):
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    modules = ctf_mgr.module_mgr.list_modules()
    header = ["Name", "Path"]
    values = [[name, str(path.resolve())] for name, path in modules.items()]

    get_view(format).print_data(header, values)


@module.command(name="get-path")
@module_name_option
@click.pass_context
def get(ctx: click.Context, module_name: str):
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    try:
        path = ctf_mgr.module_mgr.get_path(module_name)
        click.echo(str(path.resolve()))
    except ModuleNotExistsException as e:
        click.echo(e)
        exit(1)


@module.command(name="referenced")
@click.option(
    "-pn",
    "--project-name",
    type=str,
    help="Project's name. If not set, the tool will do the referencing on all data.",
)
@format_option
@click.pass_context
def referenced(ctx: click.Context, project_name: str | None, format: str):

    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    if project_name is None:
        raise NotImplementedError()
    module_count = ctf_mgr.module_mgr.reference_count(project_name)

    header = ["Module name", "Count"]
    values = [[name, count] for name, count in module_count.items()]
    get_view(format).print_data(header, values)


@module.command(name="rm")
@module_name_option
@click.pass_context
def remove(ctx: click.Context, module_name: str):
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    try:
        ctf_mgr.module_mgr.get_path(module_name)
        ctf_mgr.module_mgr.remove_module(module_name)
    except (ModuleNotExistsException, ModuleInUseException) as e:
        click.echo(e)
        exit(1)
    click.echo(f"Module `{module_name}` successfully removed.")
