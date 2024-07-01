import json
import pprint
from dataclasses import asdict
from typing import Any

import click
from tabulate import tabulate

import fit_ctf_backend.cli as _cli
from fit_ctf_backend.ctf_manager import CTFManager
from fit_ctf_backend.exceptions import CTFException
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
    "-mu",
    "--max-nof-users",
    help="Max number of users.",
    default=1000,
    show_default=True,
    type=int,
)
@click.option(
    "-p",
    "--starting-port-bind",
    help="A starting port value for each user. Each user will received a port from the range from <starting-port-bind>"
    "to <starting-port-bind + max-nof-users>. If set to -1, the tool will automatically assign an available port value."
    "User can choose a number between 10_000 to 65_535.",
    default=-1,
    show_default=True,
    type=int,
)
@click.option(
    "-vd",
    "--volume-mount-dirname",
    help="A directory name that will contain all user home volumes for the given project. "
    "This directory will be created inside project configuration directory (<dest-dir>/<dir-name>/<volume-mount-dirname>).",
    default="_mounts",
    show_default=True,
)
@click.option(
    "-dn",
    "--dir-name",
    help="Name of the directory that will be created inside <dest-dir>. If no name is set, the directory name will be "
    "generated using project name.",
    default="",
    show_default=True,
)
@click.option(
    "-de", "--description", help="A project description.", default="", show_default=True
)
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
    max_nof_users: int,
    starting_port_bind: int,
    volume_mount_dirname: str,
    dir_name: str,
    description: str,
    compose_file: str,
):
    """Create and initialize a new project.

    This command generate a basic project from the template and stores
    it in the `dest_dir` directory. Make sure that `dest_dir` exists.\f"""
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    try:
        prj = ctf_mgr.init_project(
            name,
            dest_dir,
            max_nof_users,
            starting_port_bind,
            volume_mount_dirname,
            dir_name,
            description,
            compose_file,
        )
        click.echo(f"Project `{prj.name}` was successfully generated.")
    except CTFException as e:
        click.echo(e)


@project.command(name="ls")
@click.option(
    "-a",
    "--all",
    "_all",
    is_flag=True,
    help="Display both active and inactive projects.)",
)
@click.pass_context
def list_projects(ctx: click.Context, _all: bool):
    """Display existing projects."""
    prj_mgr: ProjectManager = ctx.parent.obj["prj_mgr"]  # pyright: ignore
    lof_prj = prj_mgr.get_projects(ignore_inactive=_all)
    if not lof_prj:
        return
    headers = list(lof_prj[0].keys())
    values = [list(i.values()) for i in lof_prj]
    click.echo(tabulate(values, headers))


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
@click.argument("project_name")
@click.pass_context
def get_config_path(ctx: click.Context, project_name: str):
    """Return directory containing project configuration files.

    PROJECT_NAME    Project's name.\f
    """
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    prj = ctf_mgr.get_project_info(project_name)
    if not prj:
        click.echo(f"Project `{project_name}` not found.")
        return

    click.echo(prj.config_root_dir)


@project.command(name="active-users")
@click.argument("project_name")
@click.pass_context
def active_users(ctx: click.Context, project_name: str):
    """Get list of active users that are enrolled to the project.

    PROJECT_NAME    Project's name.\f
    """
    prj_mgr: ProjectManager = ctx.parent.obj["prj_mgr"]  # pyright: ignore
    lof_active_users = prj_mgr.get_active_users_for_project_raw(project_name)
    if not lof_active_users:
        return
    header = list(lof_active_users[0].keys())
    values = [list(i.values()) for i in lof_active_users]
    click.echo(tabulate(values, header))


@project.command(name="generate-firewall-rules")
@click.option("-ip", "--ip-addr", required=True, help="The destination IP address.")
@click.option(
    "-o",
    "--output",
    default="firewall.sh",
    help="Destination file where the script content will be written.",
)
@click.argument("project_name")
@click.pass_context
def firewall_rules(ctx: click.Context, project_name: str, ip_addr: str, output: str):
    """Generate port forwarding rules for `firewalld`.\f

    Params:
        ctx (click.Context): Context of the argument manager.
        project_name (str): Project's name.
    """
    prj_mgr: ProjectManager = ctx.parent.obj["prj_mgr"]  # pyright: ignore
    prj_mgr.generate_port_forwarding_script(project_name, ip_addr, output)


@project.command(name="reserved-ports")
@click.pass_context
def used_ports(ctx: click.Context):
    """Returns list of reserved ports."""
    prj_mgr: ProjectManager = ctx.parent.obj["prj_mgr"]  # pyright: ignore
    lof_prj = prj_mgr.get_reserved_ports()
    if not lof_prj:
        return
    header = list(lof_prj[0].keys())
    values = [list(i.values()) for i in lof_prj]
    click.echo(tabulate(values, header))


@project.command(name="resources")
@click.argument("project_name")
@click.pass_context
def resources_usage(ctx: click.Context, project_name: str):
    """Display project resources.\f

    Params:
        ctx (click.Context): Context of the argument manager.
    """
    prj_mgr: ProjectManager = ctx.parent.obj["prj_mgr"]  # pyright: ignore
    prj_mgr.print_resource_usage(project_name)


@project.command(name="export")
@click.option(
    "-o", "--output", default="project_archive.zip", help="Final ZIP file name."
)
@click.argument("project_name")
@click.pass_context
def export_project(ctx: click.Context, project_name: str, output: str):
    """Export project configurations."""
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    ctf_mgr.prj_mgr.export_project(project_name, output)


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
    ctf_mgr.delete_project(project_name)
    click.echo("Project deleted successfully.")


@project.command("flush-db")
@click.pass_context
def flush_db(ctx: click.Context):
    """Removes all inactive projects from the database."""
    prj_mgr: ProjectManager = ctx.parent.obj["prj_mgr"]  # pyright: ignore
    prj_mgr.remove_doc_by_filter(active=False)


## MANAGE PROJECT INSTANCE


@project.group(name="server")
@click.option("-n", "--name", help="Project's name", required=True)
@click.pass_context
def server(ctx: click.Context, name: str):
    """Manage project instances."""
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


@server.command(name="status")
@click.pass_context
def status_project(ctx: click.Context):
    """Turn off the project server.\f

    Params:
        ctx (click.Context): Context of the argument manager.
    """
    context_dict: dict[str, Any] = ctx.parent.obj  # pyright: ignore
    ctf_mgr: CTFManager = context_dict["ctf_mgr"]
    name = context_dict["name"]
    ctf_mgr.prj_mgr.print_ps(name)


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


@server.command(name="build")
@click.pass_context
def update_project(ctx: click.Context):
    """Build or update project's images.

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
    prj = ctf_mgr.prj_mgr.get_doc_by_filter(name=name, active=True)
    if not prj:
        click.echo(f"Project `{name}` not found.")
        return
    ctf_mgr.user_config_mgr.stop_all_user_instances(prj)
    click.echo(prj.restart())


@server.command(name="health_check")
@click.pass_context
def health_check(ctx: click.Context):
    context_dict: dict[str, Any] = ctx.parent.obj  # pyright: ignore
    ctf_mgr: CTFManager = context_dict["ctf_mgr"]
    name: str = context_dict["name"]
    ctf_mgr.health_check(name)


@server.command(name="compile")
@click.pass_context
def compile_project(ctx: click.Context):
    """Restart the project server.\f

    Params:
        ctx (click.Context): Context of the argument manager.
    """
    context_dict: dict[str, Any] = ctx.parent.obj  # pyright: ignore
    ctf_mgr: CTFManager = context_dict["ctf_mgr"]
    name = context_dict["name"]
    prj = ctf_mgr.prj_mgr.get_doc_by_filter(name=name, active=True)
    if not prj:
        click.echo(f"Project `{name}` not found.")
        return
    prj.compile()


@server.command(name="shell_admin")
@click.pass_context
def shell_admin(ctx: click.Context):
    context_dict: dict[str, Any] = ctx.parent.obj  # pyright: ignore
    ctf_mgr: CTFManager = context_dict["ctf_mgr"]
    name: str = context_dict["name"]
    prj = ctf_mgr.prj_mgr.get_project(name)
    prj.shell_admin()


# MODULES


@project.group(name="module")
@click.pass_context
def module(ctx: click.Context):
    """Manage modules."""
    ctx.obj = ctx.parent.obj  # pyright: ignore


@module.group(name="project")
@click.option("-n", "--name", help="Project's name", required=True)
@click.pass_context
def project_modules(ctx: click.Context, name: str):
    """Manage project modules."""
    context_dict: dict[str, Any] = ctx.parent.obj  # pyright: ignore
    context_dict["name"] = name
    ctx.obj = context_dict


@project_modules.command(name="create")
@click.option("-n", "--name", required=True, help="Name of the service module.")
@click.pass_context
def create_project_module(ctx: click.Context, name: str):
    context_dict: dict[str, Any] = ctx.parent.obj  # pyright: ignore
    ctf_mgr: CTFManager = context_dict["ctf_mgr"]
    prj_name = context_dict["name"]
    ctf_mgr.prj_mgr.create_project_module(prj_name, name)


@project_modules.command(name="ls")
@click.pass_context
def list_project_modules(ctx: click.Context):
    context_dict: dict[str, Any] = ctx.parent.obj  # pyright: ignore
    ctf_mgr: CTFManager = context_dict["ctf_mgr"]
    name = context_dict["name"]
    click.echo(json.dumps(ctf_mgr.prj_mgr.list_project_modules(name), indent=4))


@project_modules.command(name="remove")
@click.option("-n", "--name", required=True, help="Name of the service module.")
@click.pass_context
def remove_project_module(ctx: click.Context, name: str):
    context_dict: dict[str, Any] = ctx.parent.obj  # pyright: ignore
    ctf_mgr: CTFManager = context_dict["ctf_mgr"]
    prj_name = context_dict["name"]
    ctf_mgr.prj_mgr.remove_project_modules(prj_name, name)


@module.group(name="user")
@click.option("-n", "--name", help="Project's name", required=True)
@click.pass_context
def user_modules(ctx: click.Context, name: str):
    """Manage user modules."""
    context_dict: dict[str, Any] = ctx.parent.obj  # pyright: ignore
    context_dict["name"] = name
    ctx.obj = context_dict


@user_modules.command(name="create")
@click.option("-n", "--name", required=True, help="Name of the service module.")
@click.pass_context
def create_user_module(ctx: click.Context, name: str):
    context_dict: dict[str, Any] = ctx.parent.obj  # pyright: ignore
    ctf_mgr: CTFManager = context_dict["ctf_mgr"]
    prj_name = context_dict["name"]
    ctf_mgr.prj_mgr.create_user_module(prj_name, name)


@user_modules.command(name="ls")
@click.pass_context
def list_user_modules(ctx: click.Context):
    context_dict: dict[str, Any] = ctx.parent.obj  # pyright: ignore
    ctf_mgr: CTFManager = context_dict["ctf_mgr"]
    name = context_dict["name"]
    click.echo(json.dumps(ctf_mgr.prj_mgr.list_user_modules(name), indent=4))


@user_modules.command(name="remove")
@click.option("-n", "--name", required=True, help="Name of the service module.")
@click.pass_context
def remove_user_modules(ctx: click.Context, name: str):
    context_dict: dict[str, Any] = ctx.parent.obj  # pyright: ignore
    ctf_mgr: CTFManager = context_dict["ctf_mgr"]
    prj_name = context_dict["name"]
    ctf_mgr.prj_mgr.remove_user_modules(prj_name, name)


@module.group(name="general")
@click.pass_context
def general_module_ops(ctx: click.Context):

    raise NotImplemented()
