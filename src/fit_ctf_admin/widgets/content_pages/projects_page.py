"""Project management page."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Checkbox, Label

from fit_ctf_admin.dto import ProjectRow
from fit_ctf_admin.screens.dialogs.confirm_dialog import ConfirmDialog
from fit_ctf_admin.screens.dialogs.input_dialog import InputDialog
from fit_ctf_admin.screens.dialogs.new_project_dialog import (
    NewProjectDialog,
    NewProjectRequest,
)
from fit_ctf_admin.widgets.core_widget import AdminPage
from fit_ctf_admin.widgets.refreshable_table import RefreshableTable

COLUMNS = ("Name", "Active", "Users", "Capacity")


class ProjectsPage(AdminPage):
    def compose(self) -> ComposeResult:
        yield Label("Projects", classes="page-title")
        with Horizontal(classes="page-toolbar"):
            yield Button("New project", variant="primary", id="projects-new-btn")
            yield Button("Export", id="projects-export-btn")
            yield Button("Disable", id="projects-disable-btn")
            yield Button("Delete", variant="error", id="projects-delete-btn")
            yield Checkbox("Show inactive", id="projects-show-inactive")
        yield RefreshableTable(id="projects-table")

    def refresh_page(self) -> None:
        include_inactive = self.query_one("#projects-show-inactive", Checkbox).value
        self.call_gateway(
            lambda: self.core.gateway.list_projects(include_inactive),
            self._fill_table,
            group="projects-load",
        )

    def _fill_table(self, rows: list[ProjectRow]) -> None:
        self.query_one("#projects-table", RefreshableTable).set_data(
            COLUMNS,
            [
                (
                    row.name,
                    "yes" if row.active else "no",
                    row.active_users,
                    row.max_nof_users,
                )
                for row in rows
            ],
            [row.name for row in rows],
        )

    @property
    def _selected_project(self) -> str | None:
        return self.query_one("#projects-table", RefreshableTable).selected_key

    @on(Checkbox.Changed, "#projects-show-inactive")
    def _filter_changed(self) -> None:
        self.refresh_page()

    @on(Button.Pressed, "#projects-new-btn")
    def _new_project(self) -> None:
        self.app.push_screen(NewProjectDialog(), self._handle_new_project)

    def _handle_new_project(self, request: NewProjectRequest | None) -> None:
        if request is None:
            return
        self.call_gateway(
            lambda: self.core.gateway.create_project(
                request.name,
                request.max_nof_users,
                request.starting_port_bind,
                request.description,
            ),
            lambda row: self._mutation_done(f"Project `{row.name}` created."),
            group="projects-mutate",
        )

    @on(Button.Pressed, "#projects-export-btn")
    def _export_project(self) -> None:
        name = self._selected_project
        if name is None:
            self.notify("Select a project first.", severity="warning")
            return
        self.app.push_screen(
            InputDialog(
                f"Export project `{name}` as ZIP",
                placeholder="output file path",
                confirm_label="Export",
                initial=f"{name}_export.zip",
            ),
            lambda path: self._do_export(name, path) if path else None,
        )

    def _do_export(self, name: str, output_path: str) -> None:
        self.notify(f"Exporting `{name}`…", timeout=3)
        self.call_gateway(
            lambda: self.core.gateway.export_project(name, output_path),
            lambda written: self.notify(f"Project `{name}` exported to `{written}`."),
            group="projects-mutate",
        )

    @on(Button.Pressed, "#projects-disable-btn")
    def _disable_project(self) -> None:
        name = self._selected_project
        if name is None:
            self.notify("Select a project first.", severity="warning")
            return
        self.app.push_screen(
            ConfirmDialog(
                f"Disable project `{name}`?",
                "Stops the project and cancels all enrollments.",
                confirm_label="Disable",
            ),
            lambda confirmed: self._do_disable(name) if confirmed else None,
        )

    def _do_disable(self, name: str) -> None:
        self.call_gateway(
            lambda: self.core.gateway.disable_project(name),
            lambda _: self._mutation_done(f"Project `{name}` disabled."),
            group="projects-mutate",
        )

    @on(Button.Pressed, "#projects-delete-btn")
    def _delete_project(self) -> None:
        name = self._selected_project
        if name is None:
            self.notify("Select a project first.", severity="warning")
            return
        self.app.push_screen(
            ConfirmDialog(
                f"Delete project `{name}`?",
                "Removes the project, its enrollments, share directory, and networks.",
            ),
            lambda confirmed: self._do_delete(name) if confirmed else None,
        )

    def _do_delete(self, name: str) -> None:
        self.call_gateway(
            lambda: self.core.gateway.delete_project(name),
            lambda _: self._mutation_done(f"Project `{name}` deleted."),
            group="projects-mutate",
        )

    def _mutation_done(self, message: str) -> None:
        self.notify(message)
        self.refresh_page()
