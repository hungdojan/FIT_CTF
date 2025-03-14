import click

from fit_ctf_backend.ctf_manager import CTFManager
from fit_ctf_utils.exceptions import CTFException


@click.group(name="project-cluster")
@click.option("-pn", "--project-name", type=str, required=True, help="Project's name.")
def project_cluster(ctx: click.Context, project_name: str):
    """Manage services of an project server cluster."""
    ctx.obj = ctx.parent.obj  # pyright: ignore
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    try:
        project = ctf_mgr.prj_mgr.get_project(project_name)
    except CTFException as e:
        click.echo(e)
        exit(1)
    ctx.obj["project"] = project


@project_cluster.command(name="start")
@click.pass_context
def start_cluster(ctx: click.Context):
    """Start user instance."""
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    project = ctx.parent.obj["project"]  # pyright: ignore
    ctf_mgr.prj_mgr.start_project_cluster(project)


@project_cluster.command(name="stop")
@click.pass_context
def stop_cluster(ctx: click.Context):
    """Stop user instance."""
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    project = ctx.parent.obj["project"]  # pyright: ignore
    ctf_mgr.prj_mgr.stop_project_cluster(project)


@project_cluster.command(name="health-check")
@click.option("--to-csv", is_flag=True, help="Export the health check to the CSV file.")
@click.pass_context
def health_check(ctx: click.Context, to_csv: bool):
    # ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    # project = ctx.parent.obj["project"]  # pyright: ignore
    raise NotImplementedError()


@project_cluster.command(name="restart")
@click.pass_context
def restart_cluster(ctx: click.Context):
    """Restart user instance."""
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    project = ctx.parent.obj["project"]  # pyright: ignore
    ctf_mgr.prj_mgr.restart_project_cluster(project)


@project_cluster.command(name="is-running")
@click.pass_context
def user_cluster_is_running(ctx: click.Context):
    """Check if user instance is running."""
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    project = ctx.parent.obj["project"]  # pyright: ignore
    click.echo(ctf_mgr.prj_mgr.project_is_running(project))


@project_cluster.command(name="compile")
@click.pass_context
def compile_compose_file(ctx: click.Context):
    """Compiles user's `compose.yaml` file.

    This step is usually done after editing its list of modules."""
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    project = ctf_mgr.prj_mgr.get_project(ctx.parent.obj["project"])  # pyright: ignore
    ctf_mgr.prj_mgr.compile_compose_file(project)


@project_cluster.command(name="build")
@click.option("-pn", "--project-name", required=True, help="Project's name.")
@click.pass_context
def build_images(ctx: click.Context, project: str):
    """Update images from user's `compose.yaml` file.

    This step is usually done after compiling the YAML file."""
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    project = ctx.parent.obj["project"]  # pyright: ignore
    ctf_mgr.prj_mgr.build_project_cluster_images(project)


@project_cluster.group(name="services")
@click.pass_context
def services(ctx: click.Context):
    """Manages services of the particular enrollment service."""
    ctx.obj = ctx.parent.obj  # pyright: ignore


@services.command(name="register")
@click.option("-sn", "--service-name", required=True, type=str, help="Service's name.")
@click.option("-mn", "--module-name", required=True, type=str, help="Module's name.")
@click.pass_context
def register_service(ctx: click.Context, service_name: str, module_name: str):
    """Register a new instance to the user enrollment."""
    # ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    raise NotImplementedError()


@services.command(name="ls")
@click.pass_context
def list_services(ctx: click.Context):
    """Display a list of services of the user enrollment."""
    raise NotImplementedError()


@services.command(name="update")
@click.option("-sn", "--service-name", required=True, help="Service's name.")
@click.pass_context
def update_service(ctx: click.Context, service_name: str):
    """Update a particular"""
    raise NotImplementedError()


@services.command(name="rm")
@click.option("-sn", "--service-name", required=True, help="Service's name.")
@click.pass_context
def remove_service(ctx: click.Context, service_name: str):
    """Remove the attached module from the user."""
    # ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    raise NotImplementedError()
