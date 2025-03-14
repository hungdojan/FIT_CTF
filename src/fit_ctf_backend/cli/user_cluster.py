from dataclasses import asdict

import click
import yaml

from fit_ctf_backend.ctf_manager import CTFManager
from fit_ctf_db_models.cluster import Service
from fit_ctf_utils import document_editor
from fit_ctf_utils.exceptions import (
    CTFException,
    ConfigurationFileNotEditedException,
    ServiceNotExistException,
    UserNotEnrolledToProjectException,
)


@click.group(name="user-cluster")
@click.option("-u", "--username", type=str, required=True, help="Account username.")
@click.option("-pn", "--project-name", type=str, required=True, help="Project's name.")
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
@click.option("--to-csv", is_flag=True, help="Export the health check to the CSV file.")
@click.pass_context
def health_check(ctx: click.Context, to_csv: bool):
    # ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    # user = ctx.parent.obj["user"]  # pyright: ignore
    # project = ctx.parent.obj["project"]  # pyright: ignore
    raise NotImplementedError()


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
@click.option("-sn", "--service-name", required=True, type=str, help="Service's name.")
@click.option("-mn", "--module-name", required=True, type=str, help="Module's name.")
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
            asdict(
                Service(
                    service_name=service_name,
                    module_name=module_name,
                    is_local=not is_not_local,
                )
            ),
            {"service_name", "module_name", "is_local"},
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

    click.echo(yaml.dump(services, default_flow_style=True))


@services.command(name="update")
@click.option("-sn", "--service-name", required=True, help="Service's name.")
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
        doc = document_editor(asdict(service), {"service_name"})
        ctf_mgr.user_enrollment_mgr.update_service(
            user, project, service_name, Service(**doc)
        )
    except ConfigurationFileNotEditedException:
        click.echo("Aborting action.")


@services.command(name="rm")
@click.option("-sn", "--service-name", required=True, help="Service's name.")
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
        click.echo(yaml.dump(asdict(service), default_flow_style=True))
