import click
from tabulate import tabulate

from fit_ctf_backend.cli.utils import (
    module_name_option,
    project_option,
    service_name_option,
    user_option,
)
from fit_ctf_backend.ctf_manager import CTFManager
from fit_ctf_models.cluster import Service
from fit_ctf_utils import color_state, document_editor
from fit_ctf_utils.config_loader.yaml_parser import YamlParser
from fit_ctf_utils.exceptions import (
    ConfigurationFileNotEditedException,
    CTFException,
    ServiceNotExistException,
    UserNotEnrolledToProjectException,
)


@click.group(name="user-cluster")
@user_option
@project_option
@click.pass_context
def user_cluster(ctx: click.Context, username: str, project_name: str):
    """Manage services of an enrolled user."""
    ctx.obj = ctx.parent.obj  # pyright: ignore
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    try:
        user, project = ctf_mgr.user_enrollment_mgr._get_user_and_project(
            username, project_name
        )
        _ = ctf_mgr.user_enrollment_mgr.get_user_enrollment(user, project)
    except CTFException as e:
        click.echo(e)
        exit(1)

    ctx.obj["user"] = user
    ctx.obj["project"] = project


@user_cluster.command(name="start")
@click.pass_context
def start_cluster(ctx: click.Context):
    """Start user instance."""
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    user = ctx.parent.obj["user"]  # pyright: ignore
    project = ctx.parent.obj["project"]  # pyright: ignore
    ctf_mgr.user_enrollment_mgr.start_user_cluster(user, project)


@user_cluster.command(name="stop")
@click.pass_context
def stop_cluster(ctx: click.Context):
    """Stop user instance."""
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    user = ctx.parent.obj["user"]  # pyright: ignore
    project = ctx.parent.obj["project"]  # pyright: ignore
    ctf_mgr.user_enrollment_mgr.stop_user_cluster(user, project)


@user_cluster.command(name="health-check")
@click.pass_context
def health_check(ctx: click.Context):
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    user = ctx.parent.obj["user"]  # pyright: ignore
    project = ctx.parent.obj["project"]  # pyright: ignore
    cluster_data = ctf_mgr.user_enrollment_mgr.user_cluster_health_check(user, project)

    header = ["Name", "Image", "State"]
    values = [[i["name"], i["image"], color_state(i["state"])] for i in cluster_data]
    click.echo(tabulate(values, header))


@user_cluster.command(name="restart")
@click.pass_context
def restart_cluster(ctx: click.Context):
    """Restart user instance."""
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    user = ctx.parent.obj["user"]  # pyright: ignore
    project = ctx.parent.obj["project"]  # pyright: ignore
    ctf_mgr.user_enrollment_mgr.restart_user_cluster(user, project)


@user_cluster.command(name="is-running")
@click.pass_context
def user_cluster_is_running(ctx: click.Context):
    """Check if user instance is running."""
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    user = ctx.parent.obj["user"]  # pyright: ignore
    project = ctx.parent.obj["project"]  # pyright: ignore
    click.echo(ctf_mgr.user_enrollment_mgr.user_cluster_is_running(user, project))


@user_cluster.command(name="compile")
@click.pass_context
def compile_compose_file(ctx: click.Context):
    """Compiles user's `compose.yaml` file.

    This step is usually done after editing its list of modules."""
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    user = ctf_mgr.user_mgr.get_user(ctx.parent.obj["user"])  # pyright: ignore
    project = ctf_mgr.prj_mgr.get_project(ctx.parent.obj["project"])  # pyright: ignore
    ctf_mgr.user_enrollment_mgr.compile_compose_file(user, project)


@user_cluster.command(name="build")
@click.pass_context
def build_images(ctx: click.Context):
    """Update images from user's `compose.yaml` file.

    This step is usually done after compiling the YAML file."""
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    user = ctx.parent.obj["user"]  # pyright: ignore
    project = ctx.parent.obj["project"]  # pyright: ignore
    ctf_mgr.user_enrollment_mgr.build_user_cluster_images(user, project)


@user_cluster.group(name="services")
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
    """Register a new instance to the user enrollment."""
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    user = ctx.parent.obj["user"]  # pyright: ignore
    project = ctx.parent.obj["project"]  # pyright: ignore
    try:
        service = ctf_mgr.user_enrollment_mgr.get_service(user, project, service_name)
        if service:
            click.echo(f"Service {service.service_name} already exists.")
    except ServiceNotExistException:
        pass

    try:
        doc = document_editor(
            ctf_mgr.user_enrollment_mgr.create_template_user_service(
                user, project, service_name, module_name, not is_not_local
            ).model_dump(),
            {"service_name"},
            "service_editor",
        )
        ctf_mgr.user_enrollment_mgr.register_service(
            user, project, service_name, Service(**doc)
        )
    except ConfigurationFileNotEditedException:
        click.echo("Aborting action.")


@services.command(name="ls")
@click.pass_context
def list_services(ctx: click.Context):
    """Display a list of services of the user enrollment."""
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    user = ctx.parent.obj["user"]  # pyright: ignore
    project = ctx.parent.obj["project"]  # pyright: ignore
    try:
        services = ctf_mgr.user_enrollment_mgr.list_services(user, project)
    except UserNotEnrolledToProjectException as e:
        click.echo(e)
        exit(1)

    services_raw = {k: v.model_dump() for k, v in services.items()}
    click.echo(YamlParser.dump_data(services_raw))


@services.command(name="update")
@service_name_option
@click.pass_context
def update_service(ctx: click.Context, service_name: str):
    """Update a particular service"""
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    user = ctx.parent.obj["user"]  # pyright: ignore
    project = ctx.parent.obj["project"]  # pyright: ignore
    try:
        service = ctf_mgr.user_enrollment_mgr.get_service(user, project, service_name)
    except ServiceNotExistException as e:
        click.echo(e)
        exit(1)

    try:
        doc = document_editor(service.model_dump(), {"service_name"}, "service_editor")
        ctf_mgr.user_enrollment_mgr.update_service(
            user, project, service_name, Service(**doc)
        )
    except ConfigurationFileNotEditedException:
        click.echo("Aborting action.")


@services.command(name="rm")
@service_name_option
@click.pass_context
def remove_service(ctx: click.Context, service_name: str):
    """Remove the attached module from the user."""
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    user = ctx.parent.obj["user"]  # pyright: ignore
    project = ctx.parent.obj["project"]  # pyright: ignore

    service = ctf_mgr.user_enrollment_mgr.remove_service(user, project, service_name)
    if not service:
        click.echo("Nothing to remove.")
    else:
        click.echo(f"Removed service {service.service_name}")
        click.echo(YamlParser.dump_data(service.model_dump()))
