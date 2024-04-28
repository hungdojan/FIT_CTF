import click

from fit_ctf_backend.demo import demo_project

#########################
## Testing CLI command ##
#########################

@click.command(name="testing", help="A command used for testing purposes.")
@click.pass_context
def testing(ctx: click.Context):
    # TODO: remove in production
    if not ctx.parent:
        click.echo("No parent")
        return

    db_name = ctx.parent.obj["db_name"]
    db_host = ctx.parent.obj["db_host"]
    demo_project(db_host, db_name)
    click.echo("Demo")

