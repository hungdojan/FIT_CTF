"""Scenario designer page: form-first editing, preview, optional layout canvas.

Opening an existing scenario is sidecar-first (exact fidelity for TUI-authored
scenarios); hand-written scenarios go through the best-effort importer and are
marked as such, or can be edited as raw template text.
"""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Button, Label, Select, TabbedContent, TabPane

from fit_ctf_admin.dto import ScenarioSummary
from fit_ctf_admin.scenario.design_model import ScenarioDesign
from fit_ctf_admin.screens.dialogs.confirm_dialog import ConfirmDialog
from fit_ctf_admin.screens.dialogs.input_dialog import InputDialog
from fit_ctf_admin.screens.raw_template_screen import RawTemplateScreen
from fit_ctf_admin.widgets.core_widget import AdminPage
from fit_ctf_admin.widgets.designer.design_canvas import DesignCanvas
from fit_ctf_admin.widgets.designer.design_form import DesignForm
from fit_ctf_admin.widgets.designer.preview_panel import PreviewPanel


class DesignerPage(AdminPage):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._design = ScenarioDesign()
        self._module_names: list[str] | None = None

    def compose(self) -> ComposeResult:
        yield Label("Scenario designer", classes="page-title")
        with Horizontal(classes="page-toolbar"):
            yield Select([], prompt="Scenario", id="designer-scenario-select")
            yield Button("Open", id="designer-open-btn")
            yield Button("Raw edit", id="designer-raw-btn")
            yield Button("New design", id="designer-new-btn")
            yield Button("Save scenario", variant="primary", id="designer-save-btn")
        yield Container(id="designer-body")

    def refresh_page(self) -> None:
        self.call_gateway(
            lambda: self.core.gateway.list_scenarios(),
            self._fill_scenario_select,
            group="designer-scenarios",
        )
        if self._module_names is None:
            self.call_gateway(
                lambda: self.core.gateway.list_module_names(),
                self._modules_loaded,
                group="designer-modules",
            )

    def _fill_scenario_select(self, rows: list[ScenarioSummary]) -> None:
        select = self.query_one("#designer-scenario-select", Select)
        current = select.value
        select.set_options((row.name, row.name) for row in rows)
        if current is not Select.BLANK and any(row.name == current for row in rows):
            select.value = current

    def _modules_loaded(self, names: list[str]) -> None:
        self._module_names = names
        self._rebuild_body()

    def _rebuild_body(self) -> None:
        self.run_worker(self._async_rebuild_body, group="designer-ui", exclusive=True)

    async def _async_rebuild_body(self) -> None:
        body = self.query_one("#designer-body", Container)
        await body.remove_children()
        with self.app.batch_update():
            tabs = TabbedContent(id="designer-tabs")
            await body.mount(tabs)
            design_pane = TabPane("Design", id="design-tab")
            preview_pane = TabPane("Compose preview", id="preview-tab")
            layout_pane = TabPane("Layout", id="layout-tab")
            await tabs.add_pane(design_pane)
            await tabs.add_pane(preview_pane)
            await tabs.add_pane(layout_pane)
            await design_pane.mount(
                DesignForm(self._design, self._module_names or ["template"], id="design-form")
            )
            await preview_pane.mount(PreviewPanel(self._design, id="designer-preview"))
            await layout_pane.mount(DesignCanvas(self._design, id="designer-canvas"))

    def _set_design(self, design: ScenarioDesign) -> None:
        self._design = design
        self._rebuild_body()

    # -- form change propagation ------------------------------------------------

    @on(DesignForm.Changed)
    def _design_changed(self) -> None:
        for preview in self.query(PreviewPanel):
            preview.refresh_preview(self._design)
        for canvas in self.query(DesignCanvas):
            canvas.refresh_blocks(self._design)

    # -- toolbar actions -----------------------------------------------------------

    @property
    def _selected_scenario(self) -> str | None:
        value = self.query_one("#designer-scenario-select", Select).value
        return None if value is Select.BLANK else str(value)

    @on(Button.Pressed, "#designer-open-btn")
    def _open(self) -> None:
        name = self._selected_scenario
        if name is None:
            self.notify("Pick a scenario first.", severity="warning")
            return
        self.call_gateway(
            lambda: self.core.gateway.designer_load(name),
            lambda result: self._opened(name, result),
            group="designer-io",
        )

    def _opened(self, name: str, result: tuple[str | None, str, str]) -> None:
        design_json, compose_text, fidelity = result
        if design_json is not None and fidelity == "sidecar":
            self._set_design(ScenarioDesign.from_json(design_json))
            self.notify(f"Opened `{name}` (designer data restored).")
        elif design_json is not None and fidelity == "imported":
            self._set_design(ScenarioDesign.from_json(design_json))
            self.notify(
                f"Opened `{name}` via best-effort import — review before saving.",
                severity="warning",
            )
        else:
            self.notify(
                f"`{name}` has no designer data — opening the raw template editor.",
                severity="warning",
            )
            self.app.push_screen(RawTemplateScreen(name, compose_text))

    @on(Button.Pressed, "#designer-raw-btn")
    def _raw_edit(self) -> None:
        name = self._selected_scenario
        if name is None:
            self.notify("Pick a scenario first.", severity="warning")
            return
        self.call_gateway(
            lambda: self.core.gateway.read_raw_template(name),
            lambda text: self.app.push_screen(RawTemplateScreen(name, text)),
            group="designer-io",
        )

    @on(Button.Pressed, "#designer-new-btn")
    def _new_design(self) -> None:
        self.app.push_screen(
            InputDialog(
                "New scenario design",
                placeholder="scenario name (lowercase slug)",
                confirm_label="Create",
            ),
            self._handle_new_design,
        )

    def _handle_new_design(self, name: str | None) -> None:
        if not name:
            return
        design = ScenarioDesign(name=name.strip())
        design.add_block("service_1")
        self._set_design(design)

    @on(Button.Pressed, "#designer-save-btn")
    def _save(self) -> None:
        self.call_gateway(
            lambda: self.core.gateway.designer_state(self._design.name),
            self._save_with_state,
            group="designer-io",
        )

    def _save_with_state(self, state: str) -> None:
        if state == "foreign":
            self.app.push_screen(
                ConfirmDialog(
                    f"Scenario `{self._design.name}` exists and was written or edited "
                    "outside the designer.",
                    "Overwriting replaces its compose template. Existing extra files "
                    "under volumes/ are kept.",
                    confirm_label="Overwrite",
                ),
                lambda confirmed: self._do_save(overwrite=True) if confirmed else None,
            )
            return
        self._do_save(overwrite=state == "ours")

    def _do_save(self, *, overwrite: bool) -> None:
        self.call_gateway(
            lambda: self.core.gateway.designer_save(self._design.to_json(), overwrite=overwrite),
            self._saved,
            group="designer-io",
        )

    def _saved(self, warnings: list[str]) -> None:
        for warning in warnings:
            self.notify(warning, severity="warning", timeout=8)
        self.notify(f"Scenario `{self._design.name}` saved.")
        self.refresh_page()

    @on(Select.Changed, "#designer-scenario-select")
    def _select_changed(self) -> None:
        pass  # opening is explicit via the Open button
