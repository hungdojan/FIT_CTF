import json

import click
from tabulate import tabulate

from fit_ctf_backend.ctf_manager import CTFManager
from fit_ctf_db_models.user import UserManager
from fit_ctf_utils.auth.auth_interface import AuthInterface
from fit_ctf_utils.constants import DEFAULT_PASSWORD_LENGTH

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
@click.pass_context
def create_user(
    ctx: click.Context,
    username: str,
    password: str,
    generate_password: bool,
    email: str,
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
    click.echo(data)


@user.command(name="create-multiple")
@click.option(
    "-dp",
    "--default-password",
    help="Set default passwords to all new users.",
)
@click.argument("filename")
@click.pass_context
def multiple_create(ctx: click.Context, filename: str, default_password: str | None):
    """Create multiple new users."""
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    try:
        usernames = []
        with open(filename, "r") as f:
            usernames = [line.strip() for line in f]

        users = ctf_mgr.user_mgr.create_multiple_users(usernames, default_password)
        click.echo(users)
    except FileNotFoundError:
        click.echo(f"File `{filename}` does not exist.")
    except PermissionError:
        click.echo(f"Permission denied to access: {filename}")


@user.command(name="ls")
@click.option(
    "-a", "--all", "_all", is_flag=True, help="Display all users (even inactive)."
)
@click.pass_context
def list_users(ctx: click.Context, _all: bool):
    """Get a list of registered users in the database."""
    user_mgr: UserManager = ctx.parent.obj["ctf_mgr"].user_mgr  # pyright: ignore
    users = user_mgr.get_list_users_raw(_all)
    if not users:
        return

    values = [list(i.values()) for i in users]
    header = list(users[0].keys())
    click.echo(tabulate(values, header))


@user.command(name="get")
@click.option("-u", "--username", required=True, help="Account username.")
@click.pass_context
def get_user_info(ctx: click.Context, username: str):
    """Get user information."""
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    user_info = ctf_mgr.user_mgr.get_user_raw(username)
    click.echo(json.dumps(user_info, indent=2))

    # lof_user_enrollments = ctf_mgr.user_enrollment_mgr.get_user_info(user)
    # headers = list(lof_user_enrollments[0].keys())
    # values = [list(i.values()) for i in lof_user_enrollments]
    # click.echo(tabulate(values, headers))


@user.command(name="enrolled-projects")
@click.option("-u", "--username", required=True, help="Account username.")
@click.option(
    "-a",
    "--all",
    is_flag=True,
    default=False,
    help="Display inactive projects as well.",
)
@click.pass_context
def enrolled_projects(ctx: click.Context, username: str, all: bool):
    """Get a list of projects that a user is enrolled to."""
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    ue_mgr = ctf_mgr.user_enrollment_mgr
    lof_prj = ue_mgr.get_enrolled_projects_raw(username, all)

    if not lof_prj:
        click.echo("User has is not enrolled to any project.")
        return

    header = list(lof_prj[0].keys())
    values = [list(i.values()) for i in lof_prj]
    click.echo(tabulate(values, header))


@user.command(name="change-password")
@click.option("-u", "--username", required=True, help="Account username.")
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


# @deprecated("do not use")
# @user.group(name="services")
# @click.option("-u", "--username", type=str, required=True, help="Account username.")
# @click.option("-pn", "--project-name", type=str, required=True, help="Project's name.")
# def services(ctx: click.Context, username: str, project_name: str):
#     """Manage services of an enrolled user."""
#     context_dict: dict = ctx.parent.obj  # pyright: ignore
#     context_dict["username"] = username
#     context_dict["project_name"] = project_name
#     ctx.obj = context_dict
#
#
# @services.command(name="start")
# @click.pass_context
# def start_user(ctx: click.Context):
#     """Start user instance."""
#     ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
#     username = ctx.parent.obj["username"]  # pyright: ignore
#     project_name = ctx.parent.obj["project_name"]  # pyright: ignore
#     ctf_mgr.start_user_instance(username, project_name)
#
#
# @user.command(name="stop")
# @click.pass_context
# def stop_user(ctx: click.Context):
#     """Stop user instance."""
#     ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
#     username = ctx.parent.obj["username"]  # pyright: ignore
#     project_name = ctx.parent.obj["project_name"]  # pyright: ignore
#     ctf_mgr.stop_user_instance(username, project_name)
#
#
# @user.command(name="restart")
# @click.pass_context
# def restart_user(ctx: click.Context):
#     """Restart user instance."""
#     ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
#     username = ctx.parent.obj["username"]  # pyright: ignore
#     project_name = ctx.parent.obj["project_name"]  # pyright: ignore
#     ctf_mgr.user_enrollment_mgr.restart_user_instance(username, project_name)
#
#
# @user.command(name="is-running")
# @click.pass_context
# def user_is_running(ctx: click.Context):
#     """Check if user instance is running."""
#     ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
#     username = ctx.parent.obj["username"]  # pyright: ignore
#     project_name = ctx.parent.obj["project_name"]  # pyright: ignore
#     click.echo(ctf_mgr.user_instance_is_running(username, project_name))
#
#
# @deprecated("do not use")
# @user.command(name="enroll")
# @click.option("-u", "--username", required=True, help="Account username.")
# @click.option("-pn", "--project-name", required=True, help="Project's name.")
# @click.pass_context
# def enroll_to_project(ctx: click.Context, username: str, project_name: str):
#     """enroll user to the project."""
#
#     context_dir: dict[str, Any] = ctx.parent.obj  # pyright: ignore
#     ctf_mgr: CTFManager = context_dir["ctf_mgr"]
#     user = ctf_mgr.user_mgr.get_user(username)
#     prj = ctf_mgr.prj_mgr.get_project(project_name)
#
#     ctf_mgr.enroll_users_to_project(user.username, prj.name)
#     click.echo(f"User `{user.username}` was enrolled to the project `{prj.name}`.")
#
#
# @deprecated("do not use")
# @user.command(name="enroll-multiple")
# @click.option("-pn", "--project-name", required=True, help="Project's name.")
# @click.argument("filename")
# @click.pass_context
# def enroll_multiple_to_project(ctx: click.Context, project_name: str, filename: str):
#     """Enroll multiple users to the project."""
#
#     ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
#     try:
#         usernames = []
#         with open(filename, "r") as f:
#             usernames = [line for line in f]
#
#         users = ctf_mgr.user_enrollment_mgr.enroll_multiple_users_to_project(
#             usernames, project_name
#         )
#         click.echo(users)
#     except FileNotFoundError:
#         click.echo(f"File `{filename}` does not exist.")
#     except PermissionError:
#         click.echo(f"Permission denied to access: {filename}")
#
#
# @deprecated("do not use")
# @user.command(name="cancel")
# @click.option("-u", "--username", required=True, help="Account username.")
# @click.option("-pn", "--project-name", required=True, help="Project's name.")
# @click.pass_context
# def cancel_from_project(ctx: click.Context, username: str, project_name: str):
#     """Remove user from the project."""
#     ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
#     ctf_mgr.user_enrollment_mgr.cancel_user_enrollment(username, project_name)
#
#
# @deprecated("do not use")
# @user.command(name="cancel-multiple")
# @click.option("-pn", "--project-name", required=True, help="Project's name.")
# @click.argument("filename")
# @click.pass_context
# def cancel_multiple_enrollment(ctx: click.Context, project_name: str, filename: str):
#     """Remove multiple users from the project."""
#
#     ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
#     try:
#         usernames = []
#         with open(filename, "r") as f:
#             usernames = [line for line in f]
#
#         users = ctf_mgr.user_enrollment_mgr.cancel_multiple_enrollments(
#             usernames, project_name
#         )
#         click.echo(users)
#     except FileNotFoundError:
#         click.echo(f"File `{filename}` does not exist.")
#     except PermissionError:
#         click.echo(f"Permission denied to access: {filename}")
#
#
# @user.command(name="compile")
# @click.option("-u", "--username", required=True, help="Account username.")
# @click.option("-pn", "--project-name", required=True, help="Project's name.")
# @click.pass_context
# def compile(ctx: click.Context, username: str, project_name: str):
#     """Compiles user's `compose.yaml` file.
#
#     This step is usually done after editing its list of modules."""
#     ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
#     ctf_mgr.user_enrollment_mgr.compile_compose(username, project_name)
#
#
# @user.command(name="build")
# @click.option("-u", "--username", required=True, help="Account username.")
# @click.option("-pn", "--project-name", required=True, help="Project's name.")
# @click.pass_context
# def build(ctx: click.Context, username: str, project_name: str):
#     """Update images from user's `compose.yaml` file.
#
#     This step is usually done after compiling the YAML file."""
#     ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
#     ctf_mgr.user_enrollment_mgr.build_user_instance(username, project_name)
#
#
# @user.group(name="module")
# @click.pass_context
# def module(ctx: click.Context):
#     """Manages user modules."""
#     ctx.obj = ctx.parent.obj  # pyright: ignore
#
#
# @module.command(name="add")
# @click.option("-u", "--username", required=True, help="Account username.")
# @click.option("-pn", "--project-name", required=True, help="Project's name.")
# @click.option("-mn", "--module-name", required=True, help="Module's name.")
# @click.pass_context
# def add_module(ctx: click.Context, username: str, project_name: str, module_name: str):
#     """Attach a project module to the user."""
#     ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
#     prj = ctf_mgr.prj_mgr.get_project(project_name)
#     module = prj.user_modules.get(module_name)
#     if not module:
#         click.echo(f"Module `{module_name}` not found in `{project_name}`.")
#         return
#     ctf_mgr.user_enrollment_mgr.add_module(username, project_name, Module(**module))
#
#
# @module.command(name="ls")
# @click.option("-u", "--username", required=True, help="Account username.")
# @click.option("-pn", "--project-name", required=True, help="Project's name.")
# @click.pass_context
# def list_modules(ctx: click.Context, username: str, project_name: str):
#     """Display a list of modules attached to the user in the selected module."""
#     raise NotImplementedError()
#
#
# @module.command(name="remove")
# @click.option("-u", "--username", required=True, help="Account username.")
# @click.option("-pn", "--project-name", required=True, help="Project's name.")
# @click.option("-mn", "--module-name", required=True, help="Module's name.")
# @click.pass_context
# def remove_module(
#     ctx: click.Context, username: str, project_name: str, module_name: str
# ):
#     """Remove the attached module from the user."""
#     ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
#     ctf_mgr.user_enrollment_mgr.remove_module(username, project_name, module_name)
