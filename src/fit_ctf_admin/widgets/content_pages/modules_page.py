"""Container module management page."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Label

from fit_ctf_admin.dto import ModuleRow
from fit_ctf_admin.screens.dialogs.build_log_screen import BuildLogScreen
from fit_ctf_admin.screens.dialogs.confirm_dialog import ConfirmDialog
from fit_ctf_admin.screens.dialogs.input_dialog import InputDialog
from fit_ctf_admin.screens.module_files_screen import ModuleFilesScreen
from fit_ctf_admin.widgets.core_widget import AdminPage
from fit_ctf_admin.widgets.refreshable_table import RefreshableTable

COLUMNS = ("Module", "References", "Path")


class ModulesPage(AdminPage):
    def compose(self) -> ComposeResult:
        yield Label("Modules", classes="page-title")
        with Horizontal(classes="page-toolbar"):
            yield Button("New module", variant="primary", id="modules-new-btn")
            yield Button("Edit files", id="modules-edit-btn")
            yield Button("Build image", id="modules-build-btn")
            yield Button("Delete", variant="error", id="modules-delete-btn")
        yield RefreshableTable(id="modules-table")

    def refresh_page(self) -> None:
        self.call_gateway(
            lambda: self.core.gateway.list_modules(), self._fill_table, group="modules-load"
        )

    def _fill_table(self, rows: list[ModuleRow]) -> None:
        self.query_one("#modules-table", RefreshableTable).set_data(
            COLUMNS,
            [(row.name, row.references, row.path) for row in rows],
            [row.name for row in rows],
        )

    @property
    def _selected_module(self) -> str | None:
        return self.query_one("#modules-table", RefreshableTable).selected_key

    @on(Button.Pressed, "#modules-new-btn")
    def _new_module(self) -> None:
        self.app.push_screen(
            InputDialog(
                "New module (from template)",
                placeholder="module name",
                confirm_label="Create",
            ),
            self._handle_new_module,
        )

    def _handle_new_module(self, name: str | None) -> None:
        if not name:
            return
        self.call_gateway(
            lambda: self.core.gateway.create_module(name),
            lambda _: self._mutation_done(
                f"Module `{name.strip()}` created. Edit its Containerfile before building."
            ),
            group="modules-mutate",
        )

    @on(Button.Pressed, "#modules-edit-btn")
    def _edit_files(self) -> None:
        name = self._selected_module
        if name is None:
            self.notify("Select a module first.", severity="warning")
            return
        self.app.push_screen(ModuleFilesScreen(name))

    @on(Button.Pressed, "#modules-build-btn")
    def _build_module(self) -> None:
        name = self._selected_module
        if name is None:
            self.notify("Select a module first.", severity="warning")
            return
        # the log window opens right away and fills while the build runs
        self.app.push_screen(
            BuildLogScreen(
                f"Building image `fit-ctf/{name}`",
                lambda on_line: self.core.gateway.build_module_stream(name, on_line),
            ),
            lambda _success: self.refresh_page(),
        )

    @on(Button.Pressed, "#modules-delete-btn")
    def _delete_module(self) -> None:
        name = self._selected_module
        if name is None:
            self.notify("Select a module first.", severity="warning")
            return
        self.app.push_screen(
            ConfirmDialog(
                f"Delete module `{name}`?",
                "Removes the module directory and its images. "
                "Fails while compiled scenarios still reference it.",
            ),
            lambda confirmed: self._do_delete(name) if confirmed else None,
        )

    def _do_delete(self, name: str) -> None:
        self.call_gateway(
            lambda: self.core.gateway.remove_module(name),
            lambda _: self._mutation_done(f"Module `{name}` deleted."),
            group="modules-mutate",
        )

    def _mutation_done(self, message: str) -> None:
        self.notify(message)
        self.refresh_page()
