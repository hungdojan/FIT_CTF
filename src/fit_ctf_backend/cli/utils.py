import pathlib

import click

project_option = click.option(
    "-pn", "--project-name", required=True, type=str, help="Project's name."
)

user_option = click.option(
    "-u", "--username", required=True, type=str, help="Account username."
)

service_name_option = click.option(
    "-sn", "--service-name", required=True, help="Service's name."
)

module_name_option = click.option(
    "-mn", "--module-name", required=True, type=str, help="Module's name."
)

format_option = click.option(
    "-f",
    "--format",
    type=click.Choice(["csv", "tabulate"]),
    default="tabulate",
    help="The output format.",
)


def yaml_suffix_validation(
    ctx: click.Context, param: click.Parameter, value: pathlib.Path
):
    if value.suffix not in {".yaml", ".yml"}:
        click.echo(
            "Unsupported file type! The file must have `.yaml` or `.yml` extension."
        )
        exit(1)
    return value
