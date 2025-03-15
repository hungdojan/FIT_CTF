import pathlib

import click

from fit_ctf_backend.cli.utils import project_option, user_option
from fit_ctf_backend.ctf_manager import CTFManager
from fit_ctf_utils.exceptions import UserEnrolledToProjectException


@click.group(name="enrollment")
@click.pass_context
def enrollment(ctx: click.Context):
    """Manage all user enrollments."""
    ctx.obj = ctx.parent.obj  # pyright: ignore


@enrollment.command(name="enroll")
@user_option
@project_option
@click.pass_context
def enroll(ctx: click.Context, username: str, project_name: str):
    """Enroll a user to a project."""
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    user = ctf_mgr.user_mgr.get_user(username)
    prj = ctf_mgr.prj_mgr.get_project(project_name)

    try:
        ctf_mgr.user_enrollment_mgr.enroll_user_to_project(user, prj)
        click.echo(f"User `{user.username}` was enrolled to the project `{prj.name}`.")
    except UserEnrolledToProjectException as e:
        click.echo(e)


@enrollment.command(name="enroll-multiple")
@project_option
@click.option(
    "-i",
    "--input_file",
    required=True,
    help="Filepath to a file with new usernames.",
    type=click.Path(path_type=pathlib.Path),
)
@click.pass_context
def enroll_multiple_to_project(
    ctx: click.Context, project_name: str, input_file: pathlib.Path
):
    """Enroll multiple users to the project."""

    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    try:
        usernames = []
        with open(input_file, "r") as f:
            usernames = [line.strip() for line in f]

        user_enrollments = ctf_mgr.user_enrollment_mgr.enroll_multiple_users_to_project(
            usernames, project_name
        )
        # TODO: process new documents
        user_ids = [ue.user_id.id for ue in user_enrollments]
        users = ctf_mgr.user_mgr.get_docs_raw(
            {"_id": {"$in": user_ids}}, {"_id": 0, "username": 1}
        )
        click.echo(users)
    except FileNotFoundError:
        click.echo(f"File `{str(input_file.resolve())}` does not exist.")
    except PermissionError:
        click.echo(f"Permission denied to access: {str(input_file.resolve())}")


@enrollment.command(name="cancel")
@user_option
@project_option
@click.pass_context
def cancel_from_project(ctx: click.Context, username: str, project_name: str):
    """Remove user from the project."""
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    ctf_mgr.user_enrollment_mgr.cancel_user_enrollment(username, project_name)


@enrollment.command(name="cancel-multiple")
@project_option
@click.option(
    "-i",
    "--input_file",
    required=True,
    help="Filepath to a file with new usernames.",
    type=click.Path(path_type=pathlib.Path),
)
@click.pass_context
def cancel_multiple_enrollment(
    ctx: click.Context, project_name: str, input_file: pathlib.Path
):
    """Remove multiple users from the project."""

    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    try:
        usernames = []
        with open(input_file, "r") as f:
            usernames = [line.strip() for line in f]

        ctf_mgr.user_enrollment_mgr.cancel_multiple_enrollments(usernames, project_name)
    except FileNotFoundError:
        click.echo(f"File `{str(input_file.resolve())}` does not exist.")
    except PermissionError:
        click.echo(f"Permission denied to access: {str(input_file.resolve())}")
