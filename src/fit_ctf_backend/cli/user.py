import pprint

import click

import fit_ctf_backend.cli as _cli
from fit_ctf_backend.constants import DEFAULT_PASSWORD_LENGTH
from fit_ctf_backend.ctf_manager import CTFManager
from fit_ctf_backend.exceptions import ProjectNotExistsException, UserNotExistsException
from fit_ctf_db_models.user import UserManager

#######################
## User CLI commands ##
#######################


@click.group(name="user")
@click.pass_context
def user(ctx: click.Context):
    """A command that manages users."""
    db_host, db_name = _cli._get_db_info()
    ctf_mgr = CTFManager(db_host, db_name)

    ctx.obj = {
        "db_host": db_host,
        "db_name": db_name,
        "ctf_mgr": ctf_mgr,
        "user_mgr": ctf_mgr.user_mgr,
    }


@user.command(name="create")
@click.option("-u", "--username", required=True, help="Account username.")
@click.option("-p", "--password", default="", help="Account password.")
@click.option("--generate-password", is_flag=True, help="Computer generate a password.")
@click.option(
    "-sd", "--shadow-dir", help="A directory where a shadow file will be created."
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
    user_mgr: UserManager = ctx.parent.obj["user_mgr"]  # pyright: ignore
    user = user_mgr.get_doc_by_filter(username=username)
    if user:
        click.echo("User exists")
        # TODO: finish
        return

    if password:
        if not user_mgr.validate_password_strength(password):
            click.echo("Password is not strong enough!")
            return
    elif generate_password:
        password = user_mgr.generate_password(DEFAULT_PASSWORD_LENGTH)

    # TODO: print password
    user = user_mgr.create_new_user(username, password, shadow_dir, email)
    # TODO:


@user.command(name="multiple_create")
@click.option("-i", "--ignore-existing", is_flag=True, help="Ignore existing users.")
@click.argument("filename")
@click.pass_context
def multiple_create(ctx: click.Context, ignore_existing: bool, filename: str):
    raise NotImplemented()


@user.command(name="ls")
@click.pass_context
def list_users(ctx: click.Context):
    """Get a list of registered users in the database."""
    user_mgr: UserManager = ctx.parent.obj["user_mgr"]  # pyright: ignore
    pprint.pprint(
        user_mgr.get_docs_raw({}, projection={"password": 0, "shadow_hash": 0})
    )


@user.command(name="active-projects")
@click.option("-u", "--username", required=True, help="Account username.")
@click.pass_context
def active_projects(ctx: click.Context, username: str):
    """Get a list of active projects that a user is assigned to."""
    user_mgr: UserManager = ctx.parent.obj["user_mgr"]  # pyright: ignore
    pprint.pprint(user_mgr.get_active_projects_for_user(username))


@user.command(name="change-password")
@click.option("-u", "--username", required=True, help="Account username.")
@click.option("-p", "--password", required=True, help="New password.")
@click.pass_context
def change_password(ctx: click.Context, username: str, password: str):
    """Update user's password."""
    raise NotImplemented()


@user.command(name="delete")
@click.option("-u", "--username", required=True, help="Account username.")
@click.pass_context
def delete_user(ctx: click.Context, username: str):
    raise NotImplemented()


@user.command(name="get")
@click.option("-u", "--username", required=True, help="Account username.")
@click.pass_context
def get_user(ctx: click.Context, username: str):
    raise NotImplemented()


@user.command(name="start")
@click.option("-u", "--username", required=True, help="Account username.")
@click.option("-pn", "--project_name", required=True, help="Project's name.")
@click.pass_context
def start_user(ctx: click.Context, username: str, project_name: str):
    raise NotImplemented()


@user.command(name="stop")
@click.option("-u", "--username", required=True, help="Account username.")
@click.option("-pn", "--project_name", required=True, help="Project's name.")
@click.pass_context
def stop_user(ctx: click.Context, username: str, project_name: str):
    raise NotImplemented()


@user.command(name="restart")
@click.option("-u", "--username", required=True, help="Account username.")
@click.option("-pn", "--project_name", required=True, help="Project's name.")
@click.pass_context
def restart_user(ctx: click.Context, username: str, project_name: str):
    raise NotImplemented()


@user.command(name="is-running")
@click.option("-u", "--username", required=True, help="Account username.")
@click.option("-pn", "--project_name", required=True, help="Project's name.")
@click.pass_context
def user_is_running(ctx: click.Context, username: str, project_name: str):
    user_mgr: UserManager = ctx.parent.obj["user_mgr"]  # pyright: ignore
    user = user_mgr.get_doc_by_filter(username=username)
    if not user:
        click.echo("User not found")
        return

    raise NotImplemented()


@user.command(name="follow")
@click.option("-u", "--username", required=True, help="Account username.")
@click.option("-pn", "--project_name", required=True, help="Project's name.")
@click.pass_context
def follow_project(ctx: click.Context, username: str, project_name: str):
    """Assign user to the project."""

    context_dir: dict[str, Any] = ctx.parent.obj  # pyright: ignore
    ctf_mgr: CTFManager = context_dir["ctf_mgr"]
    user = ctf_mgr.user_mgr.get_doc_by_filter(username=username)
    if not user:
        raise UserNotExistsException(f"User `{username}` does not exist.")
    prj = ctf_mgr.prj_mgr.get_doc_by_filter(name=project_name)
    if not prj:
        raise ProjectNotExistsException(f"Project `{project_name}` does not exist.")

    ctf_mgr.assign_users_to_project(user.username, prj.name)
    click.echo(f"User `{user.username}` was assigned to the project `{prj.name}`.")


@user.command(name="unfollow")
@click.option("-u", "--username", required=True, help="Account username.")
@click.option("-pn", "--project_name", required=True, help="Project's name.")
@click.pass_context
def unfollow_project(ctx: click.Context, username: str, project_name: str):
    raise NotImplemented()


@user.command(name="generate-from-file")
@click.option("-f", "--filename", required=True, help="A filename with usernames.")
@click.pass_context
def generate_users_from_file(ctx: click.Context, filename: str):
    raise NotImplemented()
