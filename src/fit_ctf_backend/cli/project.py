import fit_ctf_backend.cli as _cli
import click
import pprint
import sys

from dataclasses import asdict
from fit_ctf_backend.ctf_manager import CTFManager

##########################
## Project CLI commands ##
##########################


@click.group(name="project", help="A command that manages projects.")
@click.pass_context
def project(ctx: click.Context):
    db_host, db_name = _cli._get_db_info()
    ctf_mgr = CTFManager(db_host, db_name)

    ctx.obj = {
        "db_host": db_host,
        "db_name": db_name,
        "ctf_mgr": ctf_mgr,
        "prj_mgr": ctf_mgr.prj_mgr,
    }


@project.command(name="create", help="Create and initialize a new project.")
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
    "-vd",
    "--volume-mount-dir",
    help="A directory the will contain use home volumes.",
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
)
@click.pass_context
def create_project(
    ctx: click.Context,
    name: str,
    dest_dir: str,
    volume_mount_dir: str,
    dir_name: str,
    description: str,
    compose_file: str,
):
    if not ctx.parent:
        click.echo("No parent")
        return
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]
    prj = ctf_mgr.init_project(
        name, dest_dir, volume_mount_dir, dir_name, description, compose_file
    )
    click.echo(prj)


@project.command(name="get-info", help="Get project info.")
@click.argument("name")  # , help="Project's name")
@click.pass_context
def get_project_info(ctx: click.Context, name: str):
    if not ctx.parent:
        click.echo("No parent")
        return
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]
    prj = ctf_mgr.get_project_info(name)
    if prj:
        pprint.pprint(asdict(prj))
    else:
        click.echo(f"Project `{name}` not found.")


@project.command("delete", help="Delete existing project.")
@click.argument("name")
@click.pass_context
def delete_project(ctx: click.Context, name: str):
    if not ctx.parent:
        click.echo("No parent")
        return
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]
    res = ctf_mgr.delete_project(name)
    if not res:
        click.echo("Failed to delete project.")
        sys.exit(1)
    click.echo("Project deleted successfully.")


@project.command(name="start", help="Boot up the project")
@click.argument("project_name")
@click.pass_context
def start_project(ctx: click.Context, project_name: str):
    if not ctx.parent:
        click.echo("No parent")
        return
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]
    ctf_mgr.start_project(project_name)


@project.command(name="stop", help="Turn off the project")
@click.argument("project_name")
@click.pass_context
def stop_project(ctx: click.Context, project_name: str):
    if not ctx.parent:
        click.echo("No parent")
        return
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]
    ctf_mgr.stop_project(project_name)


@project.command(name="is-running", help="Check if the project is running.")
@click.argument("project_name")
@click.pass_context
def is_running(ctx: click.Context, project_name: str):
    if not ctx.parent:
        click.echo("No parent")
        return
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]
    click.echo(ctf_mgr.project_is_running(project_name))


@project.command(
    name="get-config", help="Returns directory containing project configuration files."
)
@click.option("-t", "--tree", help="Display tree format.", is_flag=True)
@click.argument("project_name")
@click.pass_context
def get_config_path(ctx: click.Context, project_name: str, tree: bool):
    if not ctx.parent:
        click.echo("No parent")
        return
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]
    prj = ctf_mgr.get_project_info(project_name)
    if not prj:
        click.echo(f"Project `{project_name}` not found.")
        return

    if tree:
        raise NotImplemented()
    else:
        click.echo(prj.config_root_dir)


@project.command(
    name="registered-users", help="Get list of users registered to the project."
)
@click.argument("project_name")
@click.pass_context
def registered_users(ctx: click.Context, project_name: str):
    raise NotImplemented()


@project.command(name="add-users", help="Add users to the project.")
@click.option("-n", "--name", help="Project's name.", required=True)
@click.option("-f", "--filename", help="A file containing list of users to add.")
@click.option("-u", "--username", help="Username of the user to add.")
@click.pass_context
def add_users(ctx: click.Context, name: str, filename: str, username: str):
    raise NotImplemented()


@project.command(name="port-forwarding", help="Get list of port forwarding.")
@click.argument("project_name")
@click.pass_context
def port_forwarding(ctx: click.Context, project_name: str):
    raise NotImplemented()

@project.command(name="remove-users", help="Remove users from the project.")
@click.option("-n", "--name", help="Project's name.", required=True)
@click.option("-f", "--filename", help="A file containing list of users to add.")
@click.option("-u", "--username", help="Username of the user to add.")
@click.pass_context
def remove_users(ctx: click.Context):
    raise NotImplemented()


@project.command(name="resources", help="Display project resources.")
@click.pass_context
def resources_usage(ctx: click.Context):
    raise NotImplemented()

