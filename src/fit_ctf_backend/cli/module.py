from pathlib import Path
from shutil import copytree, rmtree

import click

from fit_ctf_backend.ctf_manager import CTFManager
from fit_ctf_templates import TEMPLATE_DIRNAME


@click.group(name="module")
@click.pass_context
def module(ctx: click.Context):
    """Manage local modules."""
    ctx.obj = ctx.parent.obj  # pyright: ignore


@module.group(name="create")
@click.option("-n", "--name", type=str, required=True, help="Name of the module.")
@click.pass_context
def create(ctx: click.Context, name: str):
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    dst_path = ctf_mgr._paths["modules"] / name
    if dst_path.is_dir():
        click.echo(f"Module `{name}` already exists at `{str(dst_path.resolve())}`")
        exit(1)

    src_path = Path(TEMPLATE_DIRNAME) / "v1" / "modules"
    copytree(src_path, dst_path)
    click.echo(f"Module `{name}` successfully created at `{str(dst_path.resolve())}`")


@module.group(name="ls")
@click.pass_context
def lists(ctx: click.Context):
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    module_path = ctf_mgr._paths["modules"]
    for path in module_path.iterdir():
        if path.is_dir():
            click.echo(path.name)


@module.group(name="get-path")
@click.option("-n", "--name", type=str, required=True, help="Name of the module.")
@click.pass_context
def get(ctx: click.Context, name: str):
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    module_path = ctf_mgr._paths["modules"] / name
    if module_path.is_dir():
        click.echo(str(module_path.resolve()))
    else:
        click.echo(f"Could not locate module `{name}`")
        exit(1)


@module.group(name="build")
@click.option("-n", "--name", type=str, required=True, help="Name of the module.")
@click.pass_context
def build(ctx: click.Context, name: str):
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    module_path = ctf_mgr._paths["modules"] / name
    if not module_path.is_dir():
        click.echo(f"Could not locate module `{name}`")
        exit(1)

    raise NotImplementedError()


@module.group(name="rm")
@click.option("-n", "--name", type=str, required=True, help="Name of the module.")
@click.pass_context
def remove(ctx: click.Context, name: str):
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    module_path = ctf_mgr._paths["modules"] / name
    if not module_path.is_dir():
        click.echo(f"Could not locate module `{name}`")
        exit(1)

    # TODO: check if module is used in any project or user
    raise NotImplementedError()
    rmtree(module_path)
