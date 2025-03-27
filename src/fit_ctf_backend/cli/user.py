import json
import pathlib

import click

from fit_ctf_backend.cli.utils import format_option, user_option
from fit_ctf_backend.ctf_manager import CTFManager
from fit_ctf_models.user import UserManager
from fit_ctf_utils.auth.auth_interface import AuthInterface
from fit_ctf_utils.constants import DEFAULT_PASSWORD_LENGTH
from fit_ctf_utils.data_view import get_view

#######################
## User CLI commands ##
#######################


@click.group(name="user")
@click.pass_context
def user(
    ctx: click.Context,
):
    """A command for user management."""
    ctx.obj = ctx.parent.obj  # pyright: ignore


@user.command(name="create")
@click.option("-u", "--username", required=True, help="Account username.")
@click.option("-p", "--password", default="", help="Account password.")
@click.option("--generate-password", is_flag=True, help="Computer generate a password.")
@click.option("-e", "--email", help="Account email.", default="")
@format_option
@click.pass_context
def create_user(
    ctx: click.Context,
    username: str,
    password: str,
    generate_password: bool,
    email: str,
    format: str,
):
    """Create a new user."""
    user_mgr: UserManager = ctx.parent.obj["ctf_mgr"].user_mgr  # pyright: ignore
    if password:
        if not AuthInterface.validate_password_strength(password):
            click.echo("Password is not strong enough!")
            return
    elif generate_password:
        password = AuthInterface.generate_password(DEFAULT_PASSWORD_LENGTH)
    else:
        click.echo("Missing either `-p` or `--generate-password` option.")
        return

    _, data = user_mgr.create_new_user(username, password, email=email)
    # print password
    headers = ["Username", "Password"]
    values = [[data["username"], data["password"]]]
    get_view(format).print_data(headers, values)


@user.command(name="create-multiple")
@click.option(
    "-i",
    "--input_file",
    required=True,
    help="Filepath to a file with new usernames.",
    type=click.Path(path_type=pathlib.Path),
)
@click.option(
    "-dp",
    "--default-password",
    help="Set default passwords to all new users.",
)
@format_option
@click.pass_context
def multiple_create(
    ctx: click.Context,
    input_file: pathlib.Path,
    default_password: str | None,
    format: str,
):
    """Create multiple new users."""
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    try:
        usernames = []
        with open(input_file, "r") as f:
            usernames = [line.strip() for line in f]

        users = ctf_mgr.user_mgr.create_multiple_users(usernames, default_password)
        headers = ["Username", "Password"]
        values = [[user[key] for key in ["username", "password"]] for user in users]
        get_view(format).print_data(headers, values)
    except FileNotFoundError:
        click.echo(f"File `{str(input_file.resolve())}` does not exist.")
    except PermissionError:
        click.echo(f"Permission denied to access: {str(input_file.resolve())}")


@user.command(name="ls")
@format_option
@click.option(
    "-a", "--all", "_all", is_flag=True, help="Display all users (even inactive)."
)
@click.pass_context
def list_users(ctx: click.Context, format: str, _all: bool):
    """Get a list of registered users in the database."""
    user_mgr: UserManager = ctx.parent.obj["ctf_mgr"].user_mgr  # pyright: ignore
    users = user_mgr.get_users_info(None if _all else True)
    if not users:
        return

    values = [
        [
            val if key != "projects" else "\n".join(val)  # pyright: ignore
            for key, val in i.items()
        ]
        for i in users
    ]
    header = [header.capitalize() for header in users[0].keys()]
    get_view(format).print_data(header, values)


@user.command(name="get")
@user_option
@click.pass_context
def get_user_info(ctx: click.Context, username: str):
    """Get user information."""
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    user_info = ctf_mgr.user_mgr.get_user_raw(username)
    click.echo(json.dumps(user_info, indent=2))


@user.command(name="enrolled-projects")
@user_option
@format_option
@click.option(
    "-a",
    "--all",
    is_flag=True,
    default=False,
    help="Display inactive projects as well.",
)
@click.pass_context
def enrolled_projects(ctx: click.Context, username: str, format: str, all: bool):
    """Get a list of projects that a user is enrolled to."""
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    ue_mgr = ctf_mgr.user_enrollment_mgr
    lof_prj = ue_mgr.get_enrolled_projects_raw(username, all)

    if not lof_prj:
        click.echo("User has is not enrolled to any project.")
        return

    header = list(lof_prj[0].keys())
    values = [list(i.values()) for i in lof_prj]
    get_view(format).print_data(header, values)


@user.command(name="change-password")
@user_option
@click.option("-p", "--password", required=True, help="New password.")
@click.pass_context
def change_password(ctx: click.Context, username: str, password: str):
    """Update user's password."""
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    # TODO: no strength validation
    ctf_mgr.user_mgr.change_password(username, password)


@user.command(name="delete")
@click.argument("usernames", nargs=-1)
@click.pass_context
def delete_user(ctx: click.Context, usernames: list[str]):
    """Remove user from the database."""
    user_mgr: UserManager = ctx.parent.obj["ctf_mgr"].user_mgr  # pyright: ignore
    user_mgr.delete_users(usernames)
