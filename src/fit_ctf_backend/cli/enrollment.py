import click

from fit_ctf_backend.ctf_manager import CTFManager
from fit_ctf_utils.exceptions import UserEnrolledToProjectException


@click.group(name="enrollment")
@click.pass_context
def enrollment(ctx: click.Context):
    """Manage all user enrollments."""
    ctx.obj = ctx.parent.obj  # pyright: ignore


@enrollment.command(name="enroll")
@click.option("-un", "--username", required=True, help="Account username.", type=str)
@click.option(
    "-pn", "--project-name", required=True, help="Project's username.", type=str
)
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
@click.option("-pn", "--project-name", required=True, help="Project's name.")
@click.argument("filename")
@click.pass_context
def enroll_multiple_to_project(ctx: click.Context, project_name: str, filename: str):
    """Enroll multiple users to the project."""

    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    try:
        usernames = []
        with open(filename, "r") as f:
            usernames = [line for line in f]

        users = ctf_mgr.user_enrollment_mgr.enroll_multiple_users_to_project(
            usernames, project_name
        )
        click.echo(users)
    except FileNotFoundError:
        click.echo(f"File `{filename}` does not exist.")
    except PermissionError:
        click.echo(f"Permission denied to access: {filename}")


@enrollment.command(name="cancel")
@click.option("-un", "--username", required=True, help="Account username.")
@click.option("-pn", "--project-name", required=True, help="Project's name.")
@click.pass_context
def cancel_from_project(ctx: click.Context, username: str, project_name: str):
    """Remove user from the project."""
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    ctf_mgr.user_enrollment_mgr.cancel_user_enrollment(username, project_name)


@enrollment.command(name="cancel-multiple")
@click.option("-pn", "--project-name", required=True, help="Project's name.")
@click.argument("filename")
@click.pass_context
def cancel_multiple_enrollment(ctx: click.Context, project_name: str, filename: str):
    """Remove multiple users from the project."""

    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    try:
        usernames = []
        with open(filename, "r") as f:
            usernames = [line for line in f]

        users = ctf_mgr.user_enrollment_mgr.cancel_multiple_enrollments(
            usernames, project_name
        )
        click.echo(users)
    except FileNotFoundError:
        click.echo(f"File `{filename}` does not exist.")
    except PermissionError:
        click.echo(f"Permission denied to access: {filename}")
