"""CLI commands for project cluster management."""

import asyncio
import pathlib

import click

from fit_ctf.components.data_parser.yaml_parser import YamlParser
from fit_ctf.components.data_view import get_view
from fit_ctf.components.exceptions import ConfigurationFileNotEditedException
from fit_ctf.components.utils import color_state, yaml_doc_editor
from fit_ctf.ctf_app import CTFApp
from fit_ctf.exceptions import CTFBaseException
from fit_ctf.models.infra.config_models import ServiceConfig
from fit_ctf.models.infra.utils import (
    scenario_config_from_dict,
    validate_canonical_scenario_yaml_dict,
)
from fit_ctf.models.infra.utils import (
    warnings_after_secrets_trial as _warnings_after_secrets_trial,
)
from fit_ctf.models.utils.exceptions import (
    CTFModelException,
    InvalidDynamicSecretKeyException,
)
from fit_ctf_cli.cli.utils import (
    format_option,
    project_option,
    requires_database,
)


def _echo_cli_warning(message: str) -> None:
    """Print one warning line to stderr (template validation, secret trial, etc.)."""
    click.echo(f"Warning: {message}", err=True)


@click.group(name="project-cluster")
@project_option
@click.pass_context
@requires_database
def project_cluster(ctx: click.Context, project_name: str):
    """Manage project-level cluster (shared infrastructure)."""
    ctx.obj = ctx.parent.obj  # pyright: ignore
    ctf_app: CTFApp = ctx.parent.obj["ctf_app"]  # pyright: ignore
    try:
        project = ctf_app.prj_mgr.get_project(project_name)
        cluster = ctf_app.project_cluster_mgr.get_cluster(project)
    except CTFBaseException as e:
        click.echo(e)
        ctx.exit(1)
    ctx.obj["project"] = project
    ctx.obj["cluster"] = cluster


@project_cluster.command(name="start")
@click.option("-v", "--verbose", is_flag=True, help="Show compose engine output")
@click.pass_context
def start_cluster(ctx: click.Context, verbose: bool):
    """Start project cluster."""
    ctf_app: CTFApp = ctx.parent.obj["ctf_app"]  # pyright: ignore
    cluster = ctx.parent.obj["cluster"]  # pyright: ignore

    click.echo(f"Starting project cluster '{cluster.name}'...")
    error_code = asyncio.run(ctf_app.project_cluster_mgr.start_cluster(cluster, verbose=verbose))

    if error_code == 0:
        click.echo("Project cluster started successfully.")
    else:
        click.echo(f"Error starting cluster (exit code: {error_code})")
        ctx.exit(error_code)


@project_cluster.command(name="stop")
@click.option("-v", "--verbose", is_flag=True, help="Show compose engine output")
@click.pass_context
def stop_cluster(ctx: click.Context, verbose: bool):
    """Stop project cluster."""
    ctf_app: CTFApp = ctx.parent.obj["ctf_app"]  # pyright: ignore
    cluster = ctx.parent.obj["cluster"]  # pyright: ignore

    click.echo(f"Stopping project cluster '{cluster.name}'...")
    error_code = asyncio.run(ctf_app.project_cluster_mgr.stop_cluster(cluster, verbose=verbose))

    if error_code == 0:
        click.echo("Project cluster stopped successfully.")
    else:
        click.echo(f"Error stopping cluster (exit code: {error_code})")
        ctx.exit(error_code)


@project_cluster.command(name="restart")
@click.option("-v", "--verbose", is_flag=True, help="Show compose engine output")
@click.pass_context
def restart_cluster(ctx: click.Context, verbose: bool):
    """Restart project cluster."""
    ctf_app: CTFApp = ctx.parent.obj["ctf_app"]  # pyright: ignore
    cluster = ctx.parent.obj["cluster"]  # pyright: ignore

    click.echo(f"Restarting project cluster '{cluster.name}'...")
    error_code = asyncio.run(ctf_app.project_cluster_mgr.restart_cluster(cluster, verbose=verbose))

    if error_code == 0:
        click.echo("Project cluster restarted successfully.")
    else:
        click.echo(f"Error restarting cluster (exit code: {error_code})")
        ctx.exit(error_code)


@project_cluster.command(name="status")
@click.pass_context
def cluster_status(ctx: click.Context):
    """Check if project cluster is running."""
    ctf_app: CTFApp = ctx.parent.obj["ctf_app"]  # pyright: ignore
    cluster = ctx.parent.obj["cluster"]  # pyright: ignore

    is_running = asyncio.run(ctf_app.project_cluster_mgr.cluster_is_running(cluster))
    status = "RUNNING" if is_running else "STOPPED"
    click.echo(f"Project cluster '{cluster.name}': {status}")


@project_cluster.command(name="health")
@format_option
@click.pass_context
def health_check(ctx: click.Context, format: str):
    """Display health check of all services in project cluster."""
    ctf_app: CTFApp = ctx.parent.obj["ctf_app"]  # pyright: ignore
    cluster = ctx.parent.obj["cluster"]  # pyright: ignore

    cluster_data = asyncio.run(ctf_app.project_cluster_mgr.cluster_health_check(cluster))

    if not cluster_data:
        click.echo("No services running in project cluster")
        return

    header = ["Name", "Image", "State"]
    values = [
        [
            i["name"],
            i["image"],
            color_state(i["state"]) if format == "tabulate" else i["state"],
        ]
        for i in cluster_data
    ]
    get_view(format).print_data(header, values)


@project_cluster.command(name="logs")
@click.option(
    "--tail",
    default=500,
    show_default=True,
    type=int,
    help="Max lines per service",
)
@click.option("-s", "--service", default=None, help="Limit to one compose service")
@click.option(
    "--no-log-stdout",
    is_flag=True,
    help="Write logs only to LOG_DEST files, not the terminal",
)
@click.pass_context
def cluster_logs(ctx: click.Context, tail: int, service: str | None, no_log_stdout: bool):
    """Show recent container logs from the project cluster compose stack."""
    ctf_app: CTFApp = ctx.parent.obj["ctf_app"]  # pyright: ignore
    cluster = ctx.parent.obj["cluster"]  # pyright: ignore

    error_code = asyncio.run(
        ctf_app.project_cluster_mgr.compose_logs(
            cluster,
            tail=tail,
            service=service,
            to_stdout=not no_log_stdout,
        )
    )
    if error_code != 0:
        click.echo(f"Error fetching logs (exit code: {error_code})")
        ctx.exit(error_code)


@project_cluster.command(name="build")
@click.option("-v", "--verbose", is_flag=True, help="Show build output")
@click.pass_context
def build_images(ctx: click.Context, verbose: bool):
    """Build/rebuild project cluster images."""
    ctf_app: CTFApp = ctx.parent.obj["ctf_app"]  # pyright: ignore
    cluster = ctx.parent.obj["cluster"]  # pyright: ignore

    click.echo(f"Building images for project cluster '{cluster.name}'...")
    error_code = asyncio.run(
        ctf_app.project_cluster_mgr.build_cluster_images(cluster, verbose=verbose)
    )

    if error_code == 0:
        click.echo("Images built successfully.")
    else:
        click.echo(f"Error building images (exit code: {error_code})")
        ctx.exit(error_code)


@project_cluster.command(name="info")
@click.pass_context
def cluster_info(ctx: click.Context):
    """Show detailed project cluster information."""
    ctf_app: CTFApp = ctx.parent.obj["ctf_app"]  # pyright: ignore
    cluster = ctx.parent.obj["cluster"]  # pyright: ignore
    project = ctx.parent.obj["project"]  # pyright: ignore

    network_map = ctf_app.project_cluster_mgr.get_network_map(cluster)

    click.echo(f"Project Cluster: {cluster.name}")
    click.echo(f"Project: {project.name}")
    click.echo(f"Project ID: {cluster.project_id.id}")
    click.echo("\nNetworks:")
    click.echo(f"  SHARED: {network_map['shared']}")
    click.echo(f"  OPERATIONAL: {network_map['operational']}")
    click.echo(f"\nScenarios ({len(cluster.scenario_configs)}):")

    for scenario_name, config in cluster.scenario_configs.items():
        click.echo(f"  - {scenario_name}")
        click.echo(f"    Services: {len(config.service_configs)}")
        if config.secrets:
            click.echo(f"    Secrets: {', '.join(config.secrets.keys())}")


@project_cluster.command(name="list-scenarios")
@format_option
@click.pass_context
def list_scenarios(ctx: click.Context, format: str):
    """List all scenarios in project cluster."""
    cluster = ctx.parent.obj["cluster"]  # pyright: ignore

    if not cluster.scenario_configs:
        click.echo("No scenarios in project cluster")
        return

    headers = ["Scenario", "Services", "Secrets"]
    values = [
        [
            name,
            len(config.service_configs),
            len(config.secrets),
        ]
        for name, config in cluster.scenario_configs.items()
    ]

    get_view(format).print_data(headers, values)


@project_cluster.command(name="add-scenario")
@click.option("-s", "--scenario", required=True, help="Scenario name to add")
@click.option("-i", "--interactive", is_flag=True, help="Interactively set values")
@click.option(
    "-f",
    "--file",
    type=click.Path(path_type=pathlib.Path),
    help="Scenario configuration file",
)
@click.pass_context
def add_scenario(ctx: click.Context, scenario: str, interactive: bool, file: pathlib.Path | None):
    """Add a scenario to the project cluster (shared infrastructure)."""
    ctf_app: CTFApp = ctx.parent.obj["ctf_app"]  # pyright: ignore
    cluster = ctx.parent.obj["cluster"]  # pyright: ignore
    project = ctx.parent.obj["project"]  # pyright: ignore

    try:
        raw: dict
        if interactive:
            doc = {
                "secrets": {k: "" for k in ctf_app.scenario_mgr.fetch_secret_keys(scenario)},
                "service_configs": ctf_app.scenario_mgr.fetch_variables(scenario),
            }
            raw = yaml_doc_editor(doc)
        elif file:
            raw = YamlParser.load_data_file(file)
        else:
            click.echo("`--interactive` or `--file` must be set")
            ctx.exit(1)

        validate_canonical_scenario_yaml_dict(raw)
        scenario_config = scenario_config_from_dict(scenario, raw)

        ctf_app.project_cluster_mgr.create_or_update_scenario_config(
            cluster,
            scenario_config,
            template_warning_sink=_echo_cli_warning,
        )

        click.echo(f"Scenario '{scenario}' added to project cluster for project '{project.name}'")
        click.echo(
            "WARNING: Remember to update service configurations with"
            " 'project-cluster edit-service' if needed"
        )
    except ConfigurationFileNotEditedException as e:
        click.echo(e)
        ctx.exit(1)
    except CTFModelException as e:
        click.echo(f"Error: {e}")
        ctx.exit(1)


@project_cluster.command(name="remove-scenario")
@click.option("-s", "--scenario", required=True, help="Scenario name to remove")
@click.pass_context
def remove_scenario(ctx: click.Context, scenario: str):
    """Remove a scenario from the project cluster."""
    ctf_app: CTFApp = ctx.parent.obj["ctf_app"]  # pyright: ignore
    cluster = ctx.parent.obj["cluster"]  # pyright: ignore
    project = ctx.parent.obj["project"]  # pyright: ignore

    try:
        if scenario not in cluster.scenario_configs:
            click.echo(f"Scenario '{scenario}' not found in project cluster")
            ctx.exit(1)

        ctf_app.project_cluster_mgr.remove_scenario_config(cluster, scenario)
        click.echo(
            f"Scenario '{scenario}' removed from project cluster for project '{project.name}'"
        )
    except CTFModelException as e:
        click.echo(f"Error: {e}")
        ctx.exit(1)


@project_cluster.command(name="edit-service")
@click.option("-s", "--scenario", required=True, help="Scenario name")
@click.option("--service", required=True, help="Service name")
@click.option("-y", "--yes", is_flag=True, help="Confirm changes")
@click.pass_context
def edit_service_config(
    ctx: click.Context,
    scenario: str,
    service: str,
    yes: bool,
):
    """Edit service configuration with YAML editor."""
    ctf_app: CTFApp = ctx.parent.obj["ctf_app"]  # pyright: ignore
    cluster = ctx.parent.obj["cluster"]  # pyright: ignore
    project = ctx.parent.obj["project"]  # pyright: ignore

    try:
        if scenario not in cluster.scenario_configs:
            click.echo(f"Error: Scenario '{scenario}' not found in cluster")
            ctx.exit(1)

        scenario_config = cluster.scenario_configs[scenario]

        # Check if service exists
        if service in scenario_config.service_configs:
            # Edit existing service
            click.echo(f"Editing service '{service}' in scenario '{scenario}'...")
            service_data = scenario_config.service_configs[service].model_dump()
        else:
            # Create new service with empty config
            click.echo(f"Creating new service '{service}' in scenario '{scenario}'...")
            service_data = {"env_map": {}, "port_map": {}, "volume_map": {}}

        click.echo("Opening editor...")

        try:
            updated_data = yaml_doc_editor(service_data)
            click.echo("\n✓ Configuration updated")

            # Update service config
            scenario_config.service_configs[service] = ServiceConfig(**updated_data)
            try:
                tmpl_warnings = ctf_app.scenario_mgr.validate_scenario_config_against_templates(
                    scenario, scenario_config
                )
            except CTFModelException as e:
                click.echo(f"Error: {e}")
                ctx.exit(1)
            for w in tmpl_warnings:
                _echo_cli_warning(w)
            ctf_app.project_cluster_mgr.update_doc(cluster)

            click.echo(f"Service '{service}' saved to project cluster for project '{project.name}'")

            # Ask if user wants to compile now
            if yes or click.confirm("\nCompile scenario now?", default=True):
                ctf_app.project_cluster_mgr.compile_scenario(
                    cluster, scenario, template_warning_sink=_echo_cli_warning
                )
                click.echo(f"Scenario '{scenario}' compiled successfully")

        except ConfigurationFileNotEditedException:
            click.echo("\n✗ No changes made (file not modified)")

    except CTFModelException as e:
        click.echo(f"Error: {e}")
        ctx.exit(1)


@project_cluster.command(name="add-secret")
@click.option("-s", "--scenario", required=True, help="Scenario name")
@click.option("-k", "--key", required=True, help="Secret key")
@click.option("-v", "--value", required=True, help="Secret value")
@click.pass_context
def add_secret(ctx: click.Context, scenario: str, key: str, value: str):
    """Add a new secret to a scenario."""
    ctf_app: CTFApp = ctx.parent.obj["ctf_app"]  # pyright: ignore
    cluster = ctx.parent.obj["cluster"]  # pyright: ignore

    try:
        if scenario not in cluster.scenario_configs:
            click.echo(f"Error: Scenario '{scenario}' not found in cluster")
            ctx.exit(1)

        scenario_config = cluster.scenario_configs[scenario]

        if "__" in key:
            raise InvalidDynamicSecretKeyException(f"secrets key {key!r} must not contain '__'")

        if key in scenario_config.secrets:
            click.echo(f"Error: Secret '{key}' already exists. Use update-secret to modify.")
            ctx.exit(1)

        for w in _warnings_after_secrets_trial(
            ctf_app.scenario_mgr, scenario, scenario_config, {key: value}
        ):
            _echo_cli_warning(w)

        scenario_config.secrets[key] = value
        ctf_app.project_cluster_mgr.update_doc(cluster)
        click.echo(f"Secret '{key}' added to scenario '{scenario}'")

    except CTFModelException as e:
        click.echo(f"Error: {e}")
        ctx.exit(1)


@project_cluster.command(name="update-secret")
@click.option("-s", "--scenario", required=True, help="Scenario name")
@click.option("-k", "--key", required=True, help="Secret key")
@click.option("-v", "--value", required=True, help="Secret value")
@click.pass_context
def update_secret(ctx: click.Context, scenario: str, key: str, value: str):
    """Update an existing secret in a scenario."""
    ctf_app: CTFApp = ctx.parent.obj["ctf_app"]  # pyright: ignore
    cluster = ctx.parent.obj["cluster"]  # pyright: ignore

    try:
        if scenario not in cluster.scenario_configs:
            click.echo(f"Error: Scenario '{scenario}' not found in cluster")
            ctx.exit(1)

        scenario_config = cluster.scenario_configs[scenario]

        if key not in scenario_config.secrets:
            click.echo(f"Error: Secret '{key}' not found in scenario '{scenario}'")
            ctx.exit(1)

        for w in _warnings_after_secrets_trial(
            ctf_app.scenario_mgr, scenario, scenario_config, {key: value}
        ):
            _echo_cli_warning(w)

        scenario_config.secrets[key] = value
        ctf_app.project_cluster_mgr.update_doc(cluster)
        click.echo(f"Secret '{key}' updated in scenario '{scenario}'")

    except CTFModelException as e:
        click.echo(f"Error: {e}")
        ctx.exit(1)


@project_cluster.command(name="remove-secret")
@click.option("-s", "--scenario", required=True, help="Scenario name")
@click.option("-k", "--key", required=True, help="Secret key to remove")
@click.option("-y", "--yes", is_flag=True, help="Confirm removal")
@click.pass_context
def remove_secret(ctx: click.Context, scenario: str, key: str, yes: bool):
    """Remove a secret from a scenario."""
    ctf_app: CTFApp = ctx.parent.obj["ctf_app"]  # pyright: ignore
    cluster = ctx.parent.obj["cluster"]  # pyright: ignore

    try:
        if scenario not in cluster.scenario_configs:
            click.echo(f"Error: Scenario '{scenario}' not found in cluster")
            ctx.exit(1)

        scenario_config = cluster.scenario_configs[scenario]

        if key not in scenario_config.secrets:
            click.echo(f"Error: Secret '{key}' not found in scenario '{scenario}'")
            ctx.exit(1)

        if not yes and not click.confirm(f"Remove secret '{key}'?", default=False):
            click.echo("Cancelled")
            return

        # pre-run check
        try:
            warnings = _warnings_after_secrets_trial(
                ctf_app.scenario_mgr, scenario, scenario_config, {key: None}
            )
        except CTFModelException as e:
            click.echo(f"Error: {e}")
            ctx.exit(1)

        scenario_config.secrets.pop(key, None)
        for w in warnings:
            _echo_cli_warning(w)
        ctf_app.project_cluster_mgr.update_doc(cluster)
        click.echo(f"Secret '{key}' removed from scenario '{scenario}'")

    except CTFModelException as e:
        click.echo(f"Error: {e}")
        ctx.exit(1)


@project_cluster.command(name="list-secrets")
@click.option("-s", "--scenario", required=True, help="Scenario name")
@format_option
@click.pass_context
def list_secrets(ctx: click.Context, scenario: str, format: str):
    """List all secrets in a scenario."""
    cluster = ctx.parent.obj["cluster"]  # pyright: ignore

    try:
        if scenario not in cluster.scenario_configs:
            click.echo(f"Error: Scenario '{scenario}' not found in cluster")
            ctx.exit(1)

        scenario_config = cluster.scenario_configs[scenario]

        if not scenario_config.secrets:
            click.echo(f"No secrets in scenario '{scenario}'")
            return

        headers = ["Key"]
        values = [[key] for key in scenario_config.secrets.keys()]

        get_view(format).print_data(headers, values)

    except CTFModelException as e:
        click.echo(f"Error: {e}")
        ctx.exit(1)


@project_cluster.command(name="compile")
@click.option("-s", "--scenario", default=None, help="Specific scenario to compile (default: all)")
@click.pass_context
def compile_cluster(ctx: click.Context, scenario: str | None):
    """Compile project cluster scenarios."""
    ctf_app: CTFApp = ctx.parent.obj["ctf_app"]  # pyright: ignore
    cluster = ctx.parent.obj["cluster"]  # pyright: ignore

    try:
        if scenario:
            if scenario not in cluster.scenario_configs:
                click.echo(f"Scenario '{scenario}' not found in project cluster")
                ctx.exit(1)
            click.echo(f"Compiling scenario '{scenario}'...")
            ctf_app.project_cluster_mgr.compile_scenario(cluster, scenario)
            click.echo(f"Scenario '{scenario}' compiled successfully")
        else:
            click.echo("Compiling all scenarios...")
            for scenario_name in cluster.scenario_configs.keys():
                click.echo(f"  Compiling '{scenario_name}'...")
                ctf_app.project_cluster_mgr.compile_scenario(cluster, scenario_name)
            click.echo("All scenarios compiled successfully")
    except CTFModelException as e:
        click.echo(f"Error: {e}")
        ctx.exit(1)
