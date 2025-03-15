import json
import os
import pathlib
from shutil import rmtree

import click

from fit_ctf_backend.ctf_manager import CTFManager
from fit_ctf_models.project import Project
from fit_ctf_utils import document_editor


@click.group(name="debug")
@click.pass_context
def debug(ctx: click.Context):
    ctx.obj = ctx.parent.obj  # pyright: ignore


@debug.command(name="edit")
@click.pass_context
def edit(ctx: click.Context):
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    project = ctf_mgr.prj_mgr.get_docs()[0]
    doc = document_editor(project.model_dump())
    ctf_mgr.prj_mgr.update_doc(Project(**doc))


@debug.command(name="db-dump")
@click.pass_context
def db_dump(ctx: click.Context):
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    click.echo("Projects:")
    click.echo(json.dumps(ctf_mgr.prj_mgr.get_docs_raw({}, {"_id": 0}), indent=2))
    click.echo("Users:")
    click.echo(json.dumps(ctf_mgr.user_mgr.get_docs_raw({}, {"_id": 0}), indent=2))
    click.echo("User enrollments:")
    click.echo(
        json.dumps(
            ctf_mgr.user_enrollment_mgr.get_docs_raw(
                {}, {"user_id": 0, "_id": 0, "project_id": 0}
            ),
            indent=2,
        )
    )


@debug.command(name="db-clear")
@click.pass_context
def db_clear(ctx: click.Context):
    ctf_mgr: CTFManager = ctx.parent.obj["ctf_mgr"]  # pyright: ignore
    ctf_mgr.prj_mgr.remove_docs_by_filter()
    ctf_mgr.user_mgr.remove_docs_by_filter()
    ctf_mgr.user_enrollment_mgr.remove_docs_by_filter()
    data_dir = (
        pathlib.Path(os.path.dirname(os.path.realpath(__file__))).parent.parent.parent
        / "data"
    )

    if data_dir.exists():
        rmtree(data_dir)
        data_dir.mkdir()
