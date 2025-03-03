import click
from click.shell_completion import shell_complete

# some magic variables required by `click`
__SHELL_COMPLETION_VARS = {
    "program_name": "fit-ctf",
    "complete_var": "_FIT_CTF_COMPLETE",
}


@click.group(name="completion")
@click.pass_context
def completion(_: click.Context):
    """Generate a shell completion script.

    As `click` supports shell completion these commands serve as
    a shortcut for generating completion scripts for ur selected shell.
    The `click` documentation only mentions how to generate such script
    from the CLI (https://click.palletsprojects.com/en/stable/shell-completion/).

    There is no official documentation for how to use the `shell_complete` function.
    Therefore this feature can be broken in the future releases of `click`.
    """
    pass


@completion.command(name="bash")
@click.pass_context
def bash(ctx: click.Context):
    """Generate a shell complete script for Bash."""
    shell_complete(
        ctx.find_root().command,
        ctx.find_root().default_map,  # pyright: ignore
        __SHELL_COMPLETION_VARS["program_name"],
        __SHELL_COMPLETION_VARS["complete_var"],
        "bash_source",
    )


@completion.command(name="zsh")
@click.pass_context
def zsh(ctx: click.Context):
    """Generate a shell complete script for Zsh."""
    shell_complete(
        ctx.find_root().command,
        ctx.find_root().default_map,  # pyright: ignore
        __SHELL_COMPLETION_VARS["program_name"],
        __SHELL_COMPLETION_VARS["complete_var"],
        "zsh_source",
    )
