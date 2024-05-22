import pprint
import sys
from dataclasses import asdict
from typing import Any

import click

import fit_ctf_backend.cli as _cli
from fit_ctf_backend.ctf_manager import CTFManager
from fit_ctf_db_models.project import ProjectManager

##########################
## Project CLI commands ##
##########################


@click.group(name="project")
@click.pass_context
def project(ctx: click.Context):
    """A command that manages projects."""
    db_host, db_name = _cli._get_db_info()
    ctf_mgr = CTFManager(db_host, db_name)

    ctx.obj = {
        "db_host": db_host,
        "db_name": db_name,
        "ctf_mgr": ctf_mgr,
        "prj_mgr": ctf_mgr.prj_mgr,
    }


@project.command(name="create")
@click.option(
    "-n",
    "--name",
    help="Project's name (also serves as project id).",
    required=True,
)
@click.option(
    "-dd",
    "--dest-dir",
    help="A directory in which the tool will store project configurations.",
    required=True,
)
@click.option(
    "-dn",
    "--dir-name",
    help="Name of the directory that will be created inside `dest-dir`.",
    default="",
)
@click.option("-de", "--description", help="Project description", default="")
@click.option(
    "-cf",
    "--compose-file",
    help="Compose filename used for managing CTF server pods.",
    default="server_compose.yaml",
    show_default=True,
)
@click.pass_context
def create_project(
    ctx: click.Context,
    name: str,
    dest_dir: str,
    dir_name: str,
    description: str,
    compose_file: str,
):
    """Create and initialize a new project.\f"""
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    prj = ctf_mgr.init_project(
        name, dest_dir, dir_name, description, compose_file
    )
    click.echo(prj)


@project.command(name="ls")
@click.pass_context
def list_projects(ctx: click.Context):
    if not ctx.parent:
        click.echo("No parent")
        return
    prj_mgr: ProjectManager = ctx.parent.obj["prj_mgr"]
    pprint.pprint(prj_mgr.get_docs({}))


@project.command(name="get-info")
@click.argument("project_name")
@click.pass_context
def get_project_info(ctx: click.Context, project_name: str):
    """Get project info.

    PROJECT_NAME    Project's name.\f
    """
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    prj = ctf_mgr.get_project_info(project_name)
    if prj:
        pprint.pprint(asdict(prj))
    else:
        click.echo(f"Project `{project_name}` not found.")


@project.command(name="get-config")
@click.option("-t", "--tree", help="Display tree format.", is_flag=True)
@click.argument("project_name")
@click.pass_context
def get_config_path(ctx: click.Context, project_name: str, tree: bool):
    """Return directory containing project configuration files.

    PROJECT_NAME    Project's name.\f
    """
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    prj = ctf_mgr.get_project_info(project_name)
    if not prj:
        click.echo(f"Project `{project_name}` not found.")
        return

    if tree:
        raise NotImplemented()
    else:
        click.echo(prj.config_root_dir)


@project.command(name="registered-users")
@click.argument("project_name")
@click.pass_context
def registered_users(ctx: click.Context, project_name: str):
    """Get list of users registered to the project.

    PROJECT_NAME    Project's name.\f
    """
    prj_mgr: ProjectManager = ctx.parent.obj["prj_mgr"]  # pyright: ignore
    click.echo(prj_mgr.get_active_users_for_project(project_name))


@project.command(name="add-users")
@click.option("-n", "--name", help="Project's name.", required=True)
@click.option("-f", "--filename", help="A file containing list of users to add.")
@click.option("-u", "--username", help="Username of the user to add.")
@click.pass_context
def add_users(ctx: click.Context, name: str, filename: str, username: str):
    """Add users to the project.\f

    Params:
        ctx (click.Context): Context of the argument manager.
        name (str): Project's name.
        filename (str): A file containing list of users to add.
        username (str): A specific user to add to the project
    """
    raise NotImplemented()


@project.command(name="port-forwarding")
@click.argument("project_name")
@click.pass_context
def port_forwarding(ctx: click.Context, project_name: str):
    """Get list of forwarded ports to user instances.\f

    Params:
        ctx (click.Context): Context of the argument manager.
        project_name (str): Project's name.
    """
    raise NotImplemented()


@project.command(name="remove-users")
@click.option("-n", "--name", help="Project's name.", required=True)
@click.option("-f", "--filename", help="A file containing list of users to add.")
@click.option("-u", "--username", help="Username of the user to add.")
@click.pass_context
def remove_users(ctx: click.Context, name: str, filename: str, username: str):
    """Remove users from the project.\f

    Params:
        ctx (click.Context): Context of the argument manager.
        name (str): Project's name.
        filename (str): A file containing list of users to add.
        username (str): A specific user to add to the project
    """
    raise NotImplemented()


@project.command(name="resources")
@click.pass_context
def resources_usage(ctx: click.Context):
    """Display project resources.\f

    Params:
        ctx (click.Context): Context of the argument manager.
    """
    raise NotImplemented()


@project.command(name="export")
@click.argument("project_name")
@click.pass_context
def export_project(ctx: click.Context, project_name: str):
    """Export project configurations."""
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"] # pyright: ignore
    ctf_mgr.export_project_configs(project_name)


@project.command("delete")
@click.argument("project_name")
@click.pass_context
def delete_project(ctx: click.Context, project_name: str):
    """Delete existing project.

    PROJECT_NAME    Project's name.\f

    Params:
        ctx (click.Context): Context of the argument manager.
        project_name (str): Project's name.
    """
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    res = ctf_mgr.delete_project(project_name)
    if not res:
        click.echo("Failed to delete project.")
        sys.exit(1)
    click.echo("Project deleted successfully.")


## MANAGE PROJECT INSTANCE


@project.group(name="server")
@click.option("-n", "--name", help="Project's name", required=True)
@click.pass_context
def server(ctx: click.Context, name: str):
    """Managing project instances."""
    context_dict: dict[str, Any] = ctx.parent.obj  # pyright: ignore
    context_dict["name"] = name
    ctx.obj = context_dict


@server.command(name="start")
@click.pass_context
def start_project(ctx: click.Context):
    """Turn on the project server.\f

    Params:
        ctx (click.Context): Context of the argument manager.
    """
    context_dict: dict[str, Any] = ctx.parent.obj  # pyright: ignore
    ctf_mgr: CTFManager = context_dict["ctf_mgr"]
    name = context_dict["name"]
    ctf_mgr.start_project(name)


@server.command(name="stop")
@click.pass_context
def stop_project(ctx: click.Context):
    """Turn off the project server.\f

    Params:
        ctx (click.Context): Context of the argument manager.
    """
    context_dict: dict[str, Any] = ctx.parent.obj  # pyright: ignore
    ctf_mgr: CTFManager = context_dict["ctf_mgr"]
    name = context_dict["name"]
    ctf_mgr.stop_project(name)


@server.command(name="is-running")
@click.pass_context
def is_running(ctx: click.Context):
    """Check if project is running.\f

    Params:
        ctx (click.Context): Context of the argument manager.
    """
    context_dict: dict[str, Any] = ctx.parent.obj  # pyright: ignore
    ctf_mgr: CTFManager = context_dict["ctf_mgr"]
    name = context_dict["name"]
    click.echo(ctf_mgr.project_is_running(name))


@server.command(name="update")
@click.pass_context
def update_project(ctx: click.Context):
    """Update project's images.

    Params:
        ctx (click.Context): Context of the argument manager.
    """
    context_dict: dict[str, Any] = ctx.parent.obj  # pyright: ignore
    ctf_mgr: CTFManager = context_dict["ctf_mgr"]
    name = context_dict["name"]
    prj = ctf_mgr.get_project_info(name)
    if not prj:
        click.echo(f"Project `{name}` not found.")
        return
    click.echo(prj.build())


@server.command(name="restart")
@click.pass_context
def restart_project(ctx: click.Context):
    """Restart the project server.\f

    Params:
        ctx (click.Context): Context of the argument manager.
    """
    context_dict: dict[str, Any] = ctx.parent.obj  # pyright: ignore
    ctf_mgr: CTFManager = context_dict["ctf_mgr"]
    name = context_dict["name"]
    prj = ctf_mgr.get_project_info(name)
    if not prj:
        click.echo(f"Project `{name}` not found.")
        return
    click.echo(prj.restart())