import click
from dotenv import load_dotenv

from fit_ctf_backend.cli.project import project
from fit_ctf_backend.cli.user import user

load_dotenv()


@click.group("cli")
def cli():
    """A tool for CTF competition management."""
    pass


cli.add_command(project)
cli.add_command(user)


def main():
    cli()


if __name__ == "__main__":
    main()
