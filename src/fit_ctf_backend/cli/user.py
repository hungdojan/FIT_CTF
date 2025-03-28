from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

import click
from tabulate import tabulate

import fit_ctf_backend.cli as _cli
from fit_ctf_backend.constants import DEFAULT_PASSWORD_LENGTH
from fit_ctf_backend.ctf_manager import CTFManager
from fit_ctf_db_models.compose_objects import Module
from fit_ctf_db_models.user import UserManager

#######################
## User CLI commands ##
#######################


@click.group(name="user")
@click.pass_context
def user(ctx: click.Context):
    """A command for user management."""
    db_host, db_name = _cli._get_db_info()
    ctf_mgr = CTFManager(db_host, db_name)

    ctx.obj = {
        "db_host": db_host,
        "db_name": db_name,
        "ctf_mgr": ctf_mgr,
    }


@user.command(name="create")
@click.option("-u", "--username", required=True, help="Account username.")
@click.option("-p", "--password", default="", help="Account password.")
@click.option("--generate-password", is_flag=True, help="Computer generate a password.")
@click.option(
    "-sd",
    "--shadow-dir",
    help="A directory where a shadow file will be created.",
    required=True,
)
@click.option("-e", "--email", help="Account email.")
@click.pass_context
def create_user(
    ctx: click.Context,
    username: str,
    password: str,
    generate_password: bool,
    shadow_dir: str,
    email: str,
):
    """Create a new user."""
    user_mgr: UserManager = ctx.parent.obj["ctf_mgr"].user_mgr  # pyright: ignore
    if password:
        if not user_mgr.validate_password_strength(password):
            click.echo("Password is not strong enough!")
            return
    elif generate_password:
        password = user_mgr.generate_password(DEFAULT_PASSWORD_LENGTH)
    else:
        click.echo("Missing either `-p` or `--generate-password` option.")
        return

    _, data = user_mgr.create_new_user(username, password, shadow_dir, email)
    # print password
    click.echo(data)


@user.command(name="create-multiple")
@click.option(
    "-sd",
    "--shadow-dir",
    help="A directory where a shadow file will be created.",
    required=True,
)
@click.option(
    "-dp",
    "--default-password",
    help="Set default passwords to all new users.",
)
@click.argument("filename")
@click.pass_context
def multiple_create(
    ctx: click.Context, shadow_dir: str, filename: str, default_password: str | None
):
    """Create multiple new users."""
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    try:
        usernames = []
        with open(filename, "r") as f:
            usernames = [line.strip() for line in f]

        users = ctf_mgr.user_mgr.create_multiple_users(
            usernames, shadow_dir, default_password
        )
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
    filter = {} if _all else {"active": True}

    users = user_mgr.get_docs_raw(filter, {"password": 0, "shadow_hash": 0})
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
    user = ctf_mgr.user_mgr.get_user(username)
    user_info = asdict(user)
    user_info.pop("_id")
    click.echo(json.dumps(user_info, indent=2))

    lof_user_configs = ctf_mgr.user_config_mgr.get_user_info(user)
    headers = list(lof_user_configs[0].keys())
    values = [list(i.values()) for i in lof_user_configs]
    click.echo(tabulate(values, headers))


@user.command(name="active-projects")
@click.option("-u", "--username", required=True, help="Account username.")
@click.pass_context
def active_projects(ctx: click.Context, username: str):
    """Get a list of active projects that a user is enrolled to."""
    user_mgr: UserManager = ctx.parent.obj["ctf_mgr"].user_mgr  # pyright: ignore
    lof_prj = user_mgr.get_active_projects_for_user_raw(username)
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


@user.command(name="start")
@click.option("-u", "--username", required=True, help="Account username.")
@click.option("-pn", "--project-name", required=True, help="Project's name.")
@click.pass_context
def start_user(ctx: click.Context, username: str, project_name: str):
    """Start user instance."""
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    ctf_mgr.start_user_instance(username, project_name)


@user.command(name="stop")
@click.option("-u", "--username", required=True, help="Account username.")
@click.option("-pn", "--project-name", required=True, help="Project's name.")
@click.pass_context
def stop_user(ctx: click.Context, username: str, project_name: str):
    """Stop user instance."""
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    ctf_mgr.stop_user_instance(username, project_name)


@user.command(name="restart")
@click.option("-u", "--username", required=True, help="Account username.")
@click.option("-pn", "--project-name", required=True, help="Project's name.")
@click.pass_context
def restart_user(ctx: click.Context, username: str, project_name: str):
    """Restart user instance."""
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    ctf_mgr.user_config_mgr.restart_user_instance(username, project_name)


@user.command(name="is-running")
@click.option("-u", "--username", required=True, help="Account username.")
@click.option("-pn", "--project-name", required=True, help="Project's name.")
@click.pass_context
def user_is_running(ctx: click.Context, username: str, project_name: str):
    """Check if user instance is running."""
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    click.echo(ctf_mgr.user_instance_is_running(username, project_name))


@user.command(name="enroll")
@click.option("-u", "--username", required=True, help="Account username.")
@click.option("-pn", "--project-name", required=True, help="Project's name.")
@click.pass_context
def enroll_to_project(ctx: click.Context, username: str, project_name: str):
    """enroll user to the project."""

    context_dir: dict[str, Any] = ctx.parent.obj  # pyright: ignore
    ctf_mgr: CTFManager = context_dir["ctf_mgr"]
    user = ctf_mgr.user_mgr.get_user(username)
    prj = ctf_mgr.prj_mgr.get_project(project_name)

    ctf_mgr.enroll_users_to_project(user.username, prj.name)
    click.echo(f"User `{user.username}` was enrolled to the project `{prj.name}`.")


@user.command(name="enroll-multiple")
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

        users = ctf_mgr.user_config_mgr.enroll_multiple_users_to_project(
            usernames, project_name
        )
        click.echo(users)
    except FileNotFoundError:
        click.echo(f"File `{filename}` does not exist.")
    except PermissionError:
        click.echo(f"Permission denied to access: {filename}")


@user.command(name="cancel")
@click.option("-u", "--username", required=True, help="Account username.")
@click.option("-pn", "--project-name", required=True, help="Project's name.")
@click.pass_context
def cancel_from_project(ctx: click.Context, username: str, project_name: str):
    """Remove user from the project."""
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    ctf_mgr.user_config_mgr.cancel_user_enrollment(username, project_name)


@user.command(name="cancel-multiple")
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

        users = ctf_mgr.user_config_mgr.cancel_multiple_enrollments(
            usernames, project_name
        )
        click.echo(users)
    except FileNotFoundError:
        click.echo(f"File `{filename}` does not exist.")
    except PermissionError:
        click.echo(f"Permission denied to access: {filename}")


@user.command(name="compile")
@click.option("-u", "--username", required=True, help="Account username.")
@click.option("-pn", "--project-name", required=True, help="Project's name.")
@click.pass_context
def compile(ctx: click.Context, username: str, project_name: str):
    """Compiles user's `compose.yaml` file.

    This step is usually done after editing its list of modules."""
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    ctf_mgr.user_config_mgr.compile_compose(username, project_name)


@user.command(name="build")
@click.option("-u", "--username", required=True, help="Account username.")
@click.option("-pn", "--project-name", required=True, help="Project's name.")
@click.pass_context
def build(ctx: click.Context, username: str, project_name: str):
    """Update images from user's `compose.yaml` file.

    This step is usually done after compiling the YAML file."""
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    ctf_mgr.user_config_mgr.build_user_instance(username, project_name)


@user.group(name="module")
@click.pass_context
def module(ctx: click.Context):
    """Manages user modules."""
    ctx.obj = ctx.parent.obj  # pyright: ignore


@module.command(name="add")
@click.option("-u", "--username", required=True, help="Account username.")
@click.option("-pn", "--project-name", required=True, help="Project's name.")
@click.option("-mn", "--module-name", required=True, help="Module's name.")
@click.pass_context
def add_module(ctx: click.Context, username: str, project_name: str, module_name: str):
    """Attach a project module to the user."""
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    prj = ctf_mgr.prj_mgr.get_project(project_name)
    module = prj.user_modules.get(module_name)
    if not module:
        click.echo(f"Module `{module_name}` not found in `{project_name}`.")
        return
    ctf_mgr.user_config_mgr.add_module(username, project_name, Module(**module))


@module.command(name="ls")
@click.option("-u", "--username", required=True, help="Account username.")
@click.option("-pn", "--project-name", required=True, help="Project's name.")
@click.pass_context
def list_modules(ctx: click.Context, username: str, project_name: str):
    """Display a list of modules attached to the user in the selected module."""
    raise NotImplementedError()


@module.command(name="remove")
@click.option("-u", "--username", required=True, help="Account username.")
@click.option("-pn", "--project-name", required=True, help="Project's name.")
@click.option("-mn", "--module-name", required=True, help="Module's name.")
@click.pass_context
def remove_module(
    ctx: click.Context, username: str, project_name: str, module_name: str
):
    """Remove the attached module from the user."""
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    ctf_mgr.user_config_mgr.remove_module(username, project_name, module_name)
