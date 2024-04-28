import click
from dotenv import load_dotenv
from fit_ctf_backend.cli import project, user, testing

load_dotenv()

@click.group("cli")
def cli():
    pass

cli.add_command(project)
cli.add_command(user)
cli.add_command(testing)

def main():
    cli()

if __name__ == "__main__":
    main()
