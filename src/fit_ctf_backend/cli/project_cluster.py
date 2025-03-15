import click
from tabulate import tabulate

from fit_ctf_backend.cli.utils import (
    module_name_option,
    project_option,
    service_name_option,
)
from fit_ctf_backend.ctf_manager import CTFManager
from fit_ctf_models.cluster import Service
from fit_ctf_utils import color_state, document_editor
from fit_ctf_utils.config_loader.yaml_parser import YamlParser
from fit_ctf_utils.exceptions import (
    ConfigurationFileNotEditedException,
    CTFException,
    ProjectNotExistException,
    ServiceNotExistException,
)


@click.group(name="project-cluster")
@project_option
@click.pass_context
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
    """Start project cluster."""
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    project = ctx.parent.obj["project"]  # pyright: ignore
    ctf_mgr.prj_mgr.start_project_cluster(project)


@project_cluster.command(name="stop")
@click.pass_context
def stop_cluster(ctx: click.Context):
    """Stop project cluster."""
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    project = ctx.parent.obj["project"]  # pyright: ignore
    ctf_mgr.prj_mgr.stop_project_cluster(project)


@project_cluster.command(name="health-check")
@click.pass_context
def health_check(ctx: click.Context):
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    project = ctx.parent.obj["project"]  # pyright: ignore
    cluster_data = ctf_mgr.prj_mgr.health_check(project)

    header = ["Name", "Image", "State"]
    values = [[i["name"], i["image"], color_state(i["state"])] for i in cluster_data]
    click.echo(tabulate(values, header))


@project_cluster.command(name="resources")
@click.pass_context
def resources(ctx: click.Context):
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    project = ctx.parent.obj["project"]  # pyright: ignore
    click.echo(ctf_mgr.prj_mgr.get_resource_usage(project))


@project_cluster.command(name="restart")
@click.pass_context
def restart_cluster(ctx: click.Context):
    """Restart project cluster."""
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    project = ctx.parent.obj["project"]  # pyright: ignore
    ctf_mgr.prj_mgr.restart_project_cluster(project)


@project_cluster.command(name="is-running")
@click.pass_context
def project_cluster_is_running(ctx: click.Context):
    """Check if project cluster is running."""
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    project = ctx.parent.obj["project"]  # pyright: ignore
    click.echo(ctf_mgr.prj_mgr.project_is_running(project))


@project_cluster.command(name="compile")
@click.pass_context
def compile_compose_file(ctx: click.Context):
    """Compiles project's `compose.yaml` file.

    This step is usually done after editing its list of modules."""
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    project = ctf_mgr.prj_mgr.get_project(ctx.parent.obj["project"])  # pyright: ignore
    ctf_mgr.prj_mgr.compile_compose_file(project)


@project_cluster.command(name="build")
@click.pass_context
def build_images(ctx: click.Context):
    """Update images from project's `compose.yaml` file.

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
@service_name_option
@module_name_option
@click.option(
    "-L",
    "--is-not-local",
    is_flag=True,
    type=bool,
    help="Set this flag if the module-name refer to a image that will be pulled from the"
    " internet (such as docker.io or similar).",
)
@click.pass_context
def register_service(
    ctx: click.Context, service_name: str, module_name: str, is_not_local: bool
):
    """Register a new services to the project cluster."""
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    project = ctx.parent.obj["project"]  # pyright: ignore
    try:
        service = ctf_mgr.prj_mgr.get_service(project, service_name)
        if service:
            click.echo(f"Service {service.service_name} already exists.")
    except ServiceNotExistException:
        pass

    try:
        doc = document_editor(
            ctf_mgr.prj_mgr.create_template_project_service(
                project, service_name, module_name, not is_not_local
            ).model_dump(),
            {"service_name"},
            "service_editor",
        )
        ctf_mgr.prj_mgr.register_service(project, service_name, Service(**doc))
    except ConfigurationFileNotEditedException:
        click.echo("Aborting action.")


@services.command(name="ls")
@click.pass_context
def list_services(ctx: click.Context):
    """Display a list of services of the project cluster."""
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    project = ctx.parent.obj["project"]  # pyright: ignore
    try:
        services = ctf_mgr.prj_mgr.list_services(project)
    except ProjectNotExistException as e:
        click.echo(e)
        exit(1)

    services_raw = {k: v.model_dump() for k, v in services.items()}
    click.echo(YamlParser.dump_data(services_raw))


@services.command(name="update")
@service_name_option
@click.pass_context
def update_service(ctx: click.Context, service_name: str):
    """Update a particular"""
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    project = ctx.parent.obj["project"]  # pyright: ignore
    try:
        service = ctf_mgr.prj_mgr.get_service(project, service_name)
    except ServiceNotExistException as e:
        click.echo(e)
        exit(1)

    try:
        doc = document_editor(service.model_dump(), {"service_name"}, "service_editor")
        ctf_mgr.prj_mgr.update_service(project, service_name, Service(**doc))
    except ConfigurationFileNotEditedException:
        click.echo("Aborting action.")


@services.command(name="rm")
@service_name_option
@click.pass_context
def remove_service(ctx: click.Context, service_name: str):
    """Remove the registered service from the project cluster."""
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    project = ctx.parent.obj["project"]  # pyright: ignore

    service = ctf_mgr.prj_mgr.remove_service(project, service_name)
    if not service:
        click.echo("Nothing to remove.")
    else:
        click.echo(f"Removed service {service.service_name}")
        click.echo(YamlParser.dump_data(service.model_dump()))
