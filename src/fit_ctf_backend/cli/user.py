import fit_ctf_backend.cli as _cli
import click

from fit_ctf_backend.ctf_manager import CTFManager

#######################
## User CLI commands ##
#######################


@click.group("user", help="A command that manages users.")
@click.pass_context
def user(ctx: click.Context):
    db_host, db_name = _cli._get_db_info()
    ctf_mgr = CTFManager(db_host, db_name)

    ctx.obj = {
        "db_host": db_host,
        "db_name": db_name,
        "ctf_mgr": ctf_mgr,
        "user_mgr": ctf_mgr.user_mgr,
    }


# @user.command("create", help="Create a new user.")
# @click.pass_context
# def create_user(ctx: click.Context):
#     db_host, db_name = _get_db_info()
#     ctf_mgr = CTFManager(db_host, db_name)
#
#     ctx.obj = {
#         "db_host": db_host,
#         "db_name": db_name,
#         "ctf_mgr": ctf_mgr,
#         "user_mgr": ctf_mgr.user_mgr,
#     }

