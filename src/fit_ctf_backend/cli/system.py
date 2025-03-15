import click


@click.group(name="system")
@click.pass_context
def system(ctx: click.Context):
    ctx.obj = ctx.parent.obj  # pyright: ignore


@system.command(name="start-db")
@click.pass_context
def start_db(ctx: click.Context):
    # TODO:
    raise NotImplementedError()


@system.command(name="shell-db")
@click.pass_context
def shell_db(ctx: click.Context):
    # TODO:
    raise NotImplementedError()


@system.command(name="stop-db")
@click.pass_context
def stop_db(ctx: click.Context):
    # TODO:
    raise NotImplementedError()


@system.command(name="uninstall")
@click.pass_context
def uninstall(ctx: click.Context):
    # TODO:
    raise NotImplementedError()
