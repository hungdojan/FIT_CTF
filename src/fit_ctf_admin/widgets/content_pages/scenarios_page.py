"""Scenario templates and their assignment to clusters."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Label, Select

from fit_ctf_admin.dto import EnrollmentRow, ProjectRow, ScenarioSummary
from fit_ctf_admin.screens.dialogs.confirm_dialog import ConfirmDialog
from fit_ctf_admin.screens.dialogs.text_dialog import TextDialog
from fit_ctf_admin.screens.scenario_config_screen import ScenarioConfigScreen
from fit_ctf_admin.widgets.core_widget import AdminPage
from fit_ctf_admin.widgets.refreshable_table import RefreshableTable

TEMPLATE_COLUMNS = ("Scenario", "Used by user clusters")
ASSIGNED_COLUMNS = ("Assigned scenario",)
KIND_OPTIONS = [("Project cluster", "project"), ("User cluster", "user")]


class ScenariosPage(AdminPage):
    def compose(self) -> ComposeResult:
        yield Label("Scenarios", classes="page-title")
        yield Label("Scenario templates (create new ones in the Designer)")
        with Horizontal(classes="page-toolbar"):
            yield Button("View template", id="scenario-view-btn")
            yield Button("Delete", variant="error", id="scenario-delete-btn")
        yield RefreshableTable(id="scenario-templates-table")
        yield Label("Assignment target")
        with Horizontal(classes="page-toolbar"):
            yield Select(
                KIND_OPTIONS,
                value="project",
                allow_blank=False,
                id="target-kind-select",
            )
            yield Select([], prompt="Project", id="target-project-select")
            yield Select([], prompt="User", id="target-user-select", disabled=True)
        with Horizontal(classes="page-toolbar"):
            yield Button("Assign selected scenario", variant="primary", id="scenario-assign-btn")
            yield Button("Edit config", id="scenario-edit-btn")
            yield Button("Recompile", id="scenario-compile-btn")
            yield Button("Unassign", variant="error", id="scenario-unassign-btn")
        yield RefreshableTable(id="assigned-scenarios-table")

    def refresh_page(self) -> None:
        self.call_gateway(
            lambda: self.core.gateway.list_scenarios(),
            self._fill_templates,
            group="scenarios-templates",
        )
        self.call_gateway(
            lambda: self.core.gateway.list_projects(),
            self._fill_projects,
            group="scenarios-projects",
        )
        self._load_assigned()

    # -- template list -------------------------------------------------------

    def _fill_templates(self, rows: list[ScenarioSummary]) -> None:
        self.query_one("#scenario-templates-table", RefreshableTable).set_data(
            TEMPLATE_COLUMNS,
            [(row.name, row.user_cluster_count) for row in rows],
            [row.name for row in rows],
        )

    @property
    def _selected_template(self) -> str | None:
        return self.query_one("#scenario-templates-table", RefreshableTable).selected_key

    @on(Button.Pressed, "#scenario-view-btn")
    def _view_template(self) -> None:
        name = self._selected_template
        if name is None:
            self.notify("Select a scenario first.", severity="warning")
            return
        self.call_gateway(
            lambda: self.core.gateway.read_raw_template(name),
            lambda text: self.app.push_screen(
                TextDialog(f"Template of `{name}` (read-only)", text)
            ),
            group="scenarios-view",
        )

    @on(Button.Pressed, "#scenario-delete-btn")
    def _delete_scenario(self) -> None:
        name = self._selected_template
        if name is None:
            self.notify("Select a scenario first.", severity="warning")
            return
        self.app.push_screen(
            ConfirmDialog(
                f"Delete scenario `{name}`?",
                "Removes the scenario template directory. Fails if it is still assigned.",
            ),
            lambda confirmed: self._do_delete(name) if confirmed else None,
        )

    def _do_delete(self, name: str) -> None:
        self.call_gateway(
            lambda: self.core.gateway.delete_scenario(name),
            lambda _: self._mutation_done(f"Scenario `{name}` deleted."),
            group="scenarios-mutate",
        )

    # -- target pickers --------------------------------------------------------

    def _fill_projects(self, projects: list[ProjectRow]) -> None:
        select = self.query_one("#target-project-select", Select)
        current = select.value
        select.set_options((p.name, p.name) for p in projects)
        if current is not Select.BLANK and any(p.name == current for p in projects):
            select.value = current

    @property
    def _target(self) -> tuple[str, str, str | None] | None:
        """Return ``(kind, project, username)`` or ``None`` when incomplete."""
        kind = str(self.query_one("#target-kind-select", Select).value)
        project = self.query_one("#target-project-select", Select).value
        if project is Select.BLANK:
            return None
        if kind == "user":
            username = self.query_one("#target-user-select", Select).value
            if username is Select.BLANK:
                return None
            return kind, str(project), str(username)
        return kind, str(project), None

    @on(Select.Changed, "#target-kind-select")
    def _kind_changed(self, event: Select.Changed) -> None:
        user_select = self.query_one("#target-user-select", Select)
        user_select.disabled = event.value != "user"
        if event.value == "user":
            self._load_target_users()
        self._load_assigned()

    @on(Select.Changed, "#target-project-select")
    def _project_changed(self) -> None:
        if str(self.query_one("#target-kind-select", Select).value) == "user":
            self._load_target_users()
        self._load_assigned()

    @on(Select.Changed, "#target-user-select")
    def _user_changed(self) -> None:
        self._load_assigned()

    def _load_target_users(self) -> None:
        project = self.query_one("#target-project-select", Select).value
        if project is Select.BLANK:
            return
        self.call_gateway(
            lambda: self.core.gateway.list_enrollments(str(project)),
            self._fill_users,
            group="scenarios-users",
        )

    def _fill_users(self, rows: list[EnrollmentRow]) -> None:
        select = self.query_one("#target-user-select", Select)
        current = select.value
        select.set_options((row.username, row.username) for row in rows)
        if current is not Select.BLANK and any(row.username == current for row in rows):
            select.value = current

    # -- assigned scenarios ----------------------------------------------------

    def _load_assigned(self) -> None:
        target = self._target
        table = self.query_one("#assigned-scenarios-table", RefreshableTable)
        if target is None:
            table.set_data(ASSIGNED_COLUMNS, [], [])
            return
        kind, project, username = target
        self.call_gateway(
            lambda: self.core.gateway.assigned_scenarios(kind, project, username),
            self._fill_assigned,
            group="scenarios-assigned",
        )

    def _fill_assigned(self, names: list[str]) -> None:
        self.query_one("#assigned-scenarios-table", RefreshableTable).set_data(
            ASSIGNED_COLUMNS, [(name,) for name in names], names
        )

    @property
    def _selected_assigned(self) -> str | None:
        return self.query_one("#assigned-scenarios-table", RefreshableTable).selected_key

    @on(Button.Pressed, "#scenario-assign-btn")
    def _assign(self) -> None:
        scenario = self._selected_template
        if scenario is None:
            self.notify("Select a scenario template first.", severity="warning")
            return
        self._open_config_editor(scenario)

    @on(Button.Pressed, "#scenario-edit-btn")
    def _edit(self) -> None:
        scenario = self._selected_assigned
        if scenario is None:
            self.notify("Select an assigned scenario first.", severity="warning")
            return
        self._open_config_editor(scenario)

    def _open_config_editor(self, scenario: str) -> None:
        target = self._target
        if target is None:
            self.notify("Pick a target cluster first.", severity="warning")
            return
        kind, project, username = target
        self.call_gateway(
            lambda: self.core.gateway.scenario_config_draft(kind, project, username, scenario),
            lambda draft: self.app.push_screen(
                ScenarioConfigScreen(kind, project, username, scenario, draft),
                lambda saved: self._load_assigned() if saved else None,
            ),
            group="scenarios-draft",
        )

    @on(Button.Pressed, "#scenario-compile-btn")
    def _recompile(self) -> None:
        scenario = self._selected_assigned
        target = self._target
        if scenario is None or target is None:
            self.notify("Select an assigned scenario first.", severity="warning")
            return
        kind, project, username = target
        self.call_gateway(
            lambda: self.core.gateway.compile_scenario(kind, project, username, scenario),
            lambda warnings: self._compile_done(scenario, warnings),
            group="scenarios-mutate",
        )

    def _compile_done(self, scenario: str, warnings: list[str]) -> None:
        for warning in warnings:
            self.notify(warning, severity="warning")
        self.notify(f"Scenario `{scenario}` compiled.")

    @on(Button.Pressed, "#scenario-unassign-btn")
    def _unassign(self) -> None:
        scenario = self._selected_assigned
        target = self._target
        if scenario is None or target is None:
            self.notify("Select an assigned scenario first.", severity="warning")
            return
        kind, project, username = target
        self.app.push_screen(
            ConfirmDialog(
                f"Unassign scenario `{scenario}`?",
                "Removes the config from the cluster and deletes its compiled files.",
                confirm_label="Unassign",
            ),
            lambda confirmed: (
                self._do_unassign(kind, project, username, scenario) if confirmed else None
            ),
        )

    def _do_unassign(self, kind: str, project: str, username: str | None, scenario: str) -> None:
        self.call_gateway(
            lambda: self.core.gateway.unassign_scenario(kind, project, username, scenario),
            lambda _: self._mutation_done(f"Scenario `{scenario}` unassigned."),
            group="scenarios-mutate",
        )

    def _mutation_done(self, message: str) -> None:
        self.notify(message)
        self.refresh_page()
