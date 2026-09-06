"""Editor for a scenario config on one cluster (assign and edit use it alike).

Secrets and config params are edited as key/value rows; the nested
``service_configs`` mapping (env/port/volume maps per service) is edited as
YAML — the same canonical document the CLI's ``add-scenario --interactive``
opens in ``$EDITOR``. Save runs the full template validation and, on success,
persists and compiles via ``create_or_update_scenario_config``.
"""

from __future__ import annotations

from functools import partial

import yaml
from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, Collapsible, Footer, Header, Label, Static, TextArea

from fit_ctf_admin.constants import ERROR_NOTIFY_TIMEOUT
from fit_ctf_admin.exceptions import AdminError
from fit_ctf_admin.screens.base_screen import BaseScreen
from fit_ctf_admin.screens.dialogs.text_dialog import TextDialog
from fit_ctf_admin.widgets.kv_editor import KeyValueEditor


class ScenarioConfigScreen(BaseScreen):
    """Pushed with a prefilled draft; dismisses ``True`` after a successful save."""

    DEFAULT_CSS = """
    ScenarioConfigScreen #config-body {
        padding: 0 2;
    }
    ScenarioConfigScreen .screen-title {
        text-style: bold;
        margin: 1 0;
    }
    ScenarioConfigScreen TextArea {
        height: 14;
        margin-bottom: 1;
    }
    ScenarioConfigScreen #config-results {
        min-height: 3;
        height: auto;
        margin: 1 0;
    }
    ScenarioConfigScreen .section-hint {
        color: $text-muted;
        margin-bottom: 1;
    }
    ScenarioConfigScreen .action-bar {
        height: auto;
        margin-bottom: 1;
    }
    ScenarioConfigScreen .action-bar Button {
        margin-right: 2;
    }
    """

    BINDINGS = [("escape", "dismiss(False)", "Cancel")]

    def __init__(
        self,
        kind: str,
        project_name: str,
        username: str | None,
        scenario: str,
        draft: dict,
    ) -> None:
        super().__init__()
        self._kind = kind
        self._project_name = project_name
        self._username = username
        self._scenario = scenario
        self._draft = draft

    @property
    def _target_label(self) -> str:
        if self._kind == "project":
            return f"project cluster `{self._project_name}`"
        return f"cluster of `{self._username}` in `{self._project_name}`"

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="config-body"):
            yield Label(
                f"Scenario `{self._scenario}` on {self._target_label}",
                classes="screen-title",
            )
            with Collapsible(title="Secrets", collapsed=False):
                yield Static(
                    "Value macro: <gen> becomes 32 random characters when you save "
                    "(<gen:16> for a custom length, FLAG{<gen>} for a wrapped flag). "
                    "The generated value is stored on the cluster.",
                    classes="section-hint",
                )
                yield KeyValueEditor(
                    self._draft.get("secrets", {}), generatable=True, id="secrets-editor"
                )
            with Collapsible(title="Service configs (YAML)", collapsed=False):
                yield TextArea(
                    yaml.safe_dump(
                        self._draft.get("service_configs", {}),
                        default_flow_style=False,
                        sort_keys=True,
                    ),
                    id="services-yaml",
                )
            with Collapsible(
                title="Config params (free template variables)",
                collapsed=not self._draft.get("config_params"),
            ):
                yield Static(
                    "Values for template variables that are not service maps or "
                    "secrets (e.g. login_node_module); injected at compile time.",
                    classes="section-hint",
                )
                yield KeyValueEditor(self._draft.get("config_params", {}), id="params-editor")
            yield Static("", id="config-results")
            with Horizontal(classes="action-bar"):
                yield Button("Validate", id="config-validate-btn")
                yield Button("Preview compiled", id="config-preview-btn")
                yield Button("Save & compile", variant="primary", id="config-save-btn")
                yield Button("Cancel", id="config-cancel-btn")
        yield Footer()

    def _collect_raw(self) -> dict | None:
        yaml_text = self.query_one("#services-yaml", TextArea).text
        try:
            services = yaml.safe_load(yaml_text) or {}
        except yaml.YAMLError as exc:
            self._show_results([f"service_configs YAML is invalid: {exc}"], [])
            return None
        if not isinstance(services, dict):
            self._show_results(["service_configs must be a YAML mapping"], [])
            return None
        return {
            "secrets": self.query_one("#secrets-editor", KeyValueEditor).data(),
            "service_configs": services,
            "config_params": self.query_one("#params-editor", KeyValueEditor).data(),
        }

    def _show_results(self, errors: list[str], warnings: list[str]) -> None:
        lines: list[str] = []
        lines.extend(f"[red]✗ {error}[/red]" for error in errors)
        lines.extend(f"[yellow]⚠ {warning}[/yellow]" for warning in warnings)
        if not lines:
            lines = ["[green]✓ Config is valid.[/green]"]
        self.query_one("#config-results", Static).update("\n".join(lines))

    @on(Button.Pressed, "#config-validate-btn")
    def _validate(self) -> None:
        raw = self._collect_raw()
        if raw is None:
            return
        self.run_worker(partial(self._run_validate, raw), exclusive=True, exit_on_error=False)

    async def _run_validate(self, raw: dict) -> None:
        try:
            errors, warnings = await self.core.gateway.validate_scenario_config(self._scenario, raw)
        except AdminError as exc:
            self.notify(str(exc), severity="error", timeout=ERROR_NOTIFY_TIMEOUT)
            return
        self._show_results(errors, warnings)

    @on(Button.Pressed, "#config-preview-btn")
    def _preview_compiled(self) -> None:
        raw = self._collect_raw()
        if raw is None:
            return
        self.run_worker(partial(self._run_preview, raw), exclusive=True, exit_on_error=False)

    async def _run_preview(self, raw: dict) -> None:
        try:
            text = await self.core.gateway.compiled_scenario_preview(self._scenario, raw)
        except AdminError as exc:
            self.notify(str(exc), severity="error", timeout=ERROR_NOTIFY_TIMEOUT)
            return
        self.app.push_screen(TextDialog(f"Compiled preview of `{self._scenario}`", text))

    @on(Button.Pressed, "#config-save-btn")
    def _save(self) -> None:
        raw = self._collect_raw()
        if raw is None:
            return
        self.run_worker(partial(self._run_save, raw), exclusive=True, exit_on_error=False)

    async def _run_save(self, raw: dict) -> None:
        gateway = self.core.gateway
        try:
            errors, warnings = await gateway.validate_scenario_config(self._scenario, raw)
            if errors:
                self._show_results(errors, warnings)
                return
            warnings = await gateway.apply_scenario_config(
                self._kind, self._project_name, self._username, self._scenario, raw
            )
        except AdminError as exc:
            self.notify(str(exc), severity="error", timeout=ERROR_NOTIFY_TIMEOUT)
            return
        for warning in warnings:
            self.notify(warning, severity="warning", timeout=ERROR_NOTIFY_TIMEOUT)
        self.notify(f"Scenario `{self._scenario}` saved and compiled on {self._target_label}.")
        self.dismiss(True)

    @on(Button.Pressed, "#config-cancel-btn")
    def _cancel(self) -> None:
        self.dismiss(False)
