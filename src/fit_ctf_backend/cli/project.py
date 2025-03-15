import click
from tabulate import tabulate

from fit_ctf_backend.cli.utils import project_option
from fit_ctf_backend.ctf_manager import CTFManager
from fit_ctf_models.project import ProjectManager
from fit_ctf_utils import color_state
from fit_ctf_utils.config_loader.yaml_parser import YamlParser
from fit_ctf_utils.exceptions import CTFException

##########################
## Project CLI commands ##
##########################


@click.group(name="project")
@click.pass_context
def project(
    ctx: click.Context,
):
    """A command for project management."""
    ctx.obj = ctx.parent.obj  # pyright: ignore


@project.command(name="create")
@click.option(
    "-pn",
    "--project-name",
    help="Project's name (also serves as project id).",
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
    help="A starting port value for each user. "
    "Each user will received a port from the range from <starting-port-bind>"
    "to <starting-port-bind + max-nof-users>. "
    "If set to -1, the tool will automatically assign an available port value."
    "User can choose a number between 10_000 to 65_535.",
    default=-1,
    show_default=True,
    type=int,
)
@click.option(
    "-de", "--description", help="A project description.", default="", show_default=True
)
@click.pass_context
def create_project(
    ctx: click.Context,
    project_name: str,
    max_nof_users: int,
    starting_port_bind: int,
    description: str,
):
    """Create and initialize a new project.

    This command generate a basic project from the template and stores
    it in the `dest_dir` directory. Make sure that `dest_dir` exists."""
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    try:
        prj = ctf_mgr.prj_mgr.init_project(
            project_name,
            max_nof_users,
            starting_port_bind,
            description,
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
    """Display existing projects.

    This command by default displays only active projects. Use `-a` flag to
    display inactive projects.

    Displays following states:
        - active state
        - project name
        - max number of users
        - number of active users enrolled to the project
    """
    prj_mgr: ProjectManager = ctx.parent.obj["ctf_mgr"].prj_mgr  # pyright: ignore
    lof_prj = prj_mgr.get_projects(include_inactive=_all)
    if not lof_prj:
        click.echo("No project found!")
        return
    headers = list(lof_prj[0].keys())
    values = [list(i.values()) for i in lof_prj]
    click.echo(tabulate(values, headers))


@project.command(name="get-info")
@project_option
@click.pass_context
def get_project_info(ctx: click.Context, project_name: str):
    """Display project PROJECT_NAME's information.

    Dumps all information about a selected project.
    """
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    prj = ctf_mgr.prj_mgr.get_doc_by_filter_raw({"name": project_name}, {"_id": 0})
    # TODO: format
    if prj:
        click.echo(YamlParser.dump_data(prj))
    else:
        click.echo(f"Project `{project_name}` not found.")


@project.command(name="enrolled-users")
@project_option
@click.option(
    "-a",
    "--all",
    is_flag=True,
    default=False,
    help="Display inactive enrollments as well.",
)
@click.pass_context
def enrolled_users(ctx: click.Context, project_name: str, all: bool):
    """Get list of active users that are enrolled to the PROJECT_NAME.

    Displays following states:
        - user ID
        - active state
        - account username
        - account role
        - path to the shadow file
        - email
        - path to home mounting directory/volume
        - forwarded port (visible from the outside)
    """
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    lof_active_users = ctf_mgr.user_enrollment_mgr.get_user_enrollments_for_project_raw(
        project_name, all
    )
    if not lof_active_users:
        click.echo("No active users found.")
        return
    header_order = ["username", "role", "active", "forwarded_port", "mount"]
    header = [" ".join([i.capitalize() for i in i.split("_")]) for i in header_order]
    values = [[i[key] for key in header_order] for i in lof_active_users]
    click.echo(tabulate(values, header, stralign="center", numalign="center"))


@project.command(name="generate-firewall-rules")
@click.option("-ip", "--ip-addr", required=True, help="The destination IP address.")
@click.option(
    "-o",
    "--output",
    default="firewall.sh",
    help="Destination file where the script content will be written.",
)
@project_option
@click.pass_context
def firewall_rules(ctx: click.Context, project_name: str, ip_addr: str, output: str):
    """Generate a BASH script with port forwarding rules for PROJECT_NAME.

    The command used in the script are written for `firewalld` application.
    """
    prj_mgr: ProjectManager = ctx.parent.obj["ctf_mgr"].prj_mgr  # pyright: ignore
    prj_mgr.generate_port_forwarding_script(project_name, ip_addr, output)


@project.command(name="reserved-ports")
@click.pass_context
def used_ports(ctx: click.Context):
    """Returns list of reserved ports.

    Displays a list of projects and their reserved port range."""
    prj_mgr: ProjectManager = ctx.parent.obj["ctf_mgr"].prj_mgr  # pyright: ignore
    lof_prj = prj_mgr.get_reserved_ports()
    if not lof_prj:
        click.echo("No project found!")
        return
    header = list(lof_prj[0].keys())
    values = [list(i.values()) for i in lof_prj]
    click.echo(tabulate(values, header))


@project.command(name="resources")
@project_option
@click.pass_context
def resources_usage(ctx: click.Context, project_name: str):
    """Display PROJECT_NAME current resource usage."""
    prj_mgr: ProjectManager = ctx.parent.obj["ctf_mgr"].prj_mgr  # pyright: ignore
    try:
        prj_mgr.get_resource_usage(project_name)
    except CTFException as e:
        click.echo(e)


@project.command("delete")
@project_option
@click.pass_context
def delete_project(ctx: click.Context, project_name: str):
    """Delete an existing project PROJECT_NAME.

    Deletes all project configuration files and sets project activity
    state to `inactive`.
    """
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    ctf_mgr.prj_mgr.delete_project(project_name)
    click.echo("Project deleted successfully.")


@project.command(name="running-cluster")
@project_option
@click.pass_context
def running_clusters_info(ctx: click.Context, project_name: str):
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    services_info = ctf_mgr.prj_mgr.get_all_services_info(project_name)
    data_buffer = []
    for info in services_info:
        data_buffer.append(
            {
                "image": info["Image"],
                "name": info["Names"][0],
                "networks": "\n".join(info["Networks"]) if info["Networks"] else "",
                "cluster_type": (
                    info["Labels"]["cluster_type"]
                    if info["Labels"].get("cluster_type")
                    else ""
                ),
                "state": color_state(info["State"]),
                "ports": (
                    "\n".join([str(p["host_port"]) for p in info["Ports"]])
                    if info["Ports"]
                    else ""
                ),
            }
        )
    # click.echo(services_info)
    header_order = ["name", "image", "cluster_type", "networks", "ports", "state"]
    header = [" ".join([i.capitalize() for i in i.split("_")]) for i in header_order]
    values = [[i[key] for key in header_order] for i in data_buffer]
    click.echo(
        tabulate(values, header, stralign="center", numalign="center", tablefmt="grid")
    )
