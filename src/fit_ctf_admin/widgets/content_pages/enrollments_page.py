"""Enrollment management page (per-project view with an all-projects option)."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Checkbox, Label, Select

from fit_ctf_admin.dto import EnrollmentRow, ProjectRow
from fit_ctf_admin.screens.dialogs.confirm_dialog import ConfirmDialog
from fit_ctf_admin.screens.dialogs.enroll_dialog import EnrollDialog
from fit_ctf_admin.widgets.core_widget import AdminPage
from fit_ctf_admin.widgets.refreshable_table import RefreshableTable

COLUMNS = ("User", "Project", "Role", "Active", "Port")
ALL_PROJECTS = "(all projects)"


class EnrollmentsPage(AdminPage):
    def compose(self) -> ComposeResult:
        yield Label("Enrollments", classes="page-title")
        with Horizontal(classes="page-toolbar"):
            yield Select(
                [(ALL_PROJECTS, ALL_PROJECTS)],
                value=ALL_PROJECTS,
                id="enrollments-project-select",
            )
            yield Button("Enroll user", variant="primary", id="enrollments-enroll-btn")
            yield Button("Cancel enrollment", variant="error", id="enrollments-cancel-btn")
            yield Checkbox("Show inactive", id="enrollments-show-inactive")
        yield RefreshableTable(id="enrollments-table")

    def refresh_page(self) -> None:
        self.call_gateway(
            lambda: self.core.gateway.list_projects(include_inactive=True),
            self._fill_project_select,
            group="enrollments-projects",
        )
        self._load_enrollments()

    def _fill_project_select(self, projects: list[ProjectRow]) -> None:
        select = self.query_one("#enrollments-project-select", Select)
        current = select.value
        options = [(ALL_PROJECTS, ALL_PROJECTS)] + [(p.name, p.name) for p in projects]
        select.set_options(options)
        values = {value for _, value in options}
        select.value = current if current in values else ALL_PROJECTS

    def _load_enrollments(self) -> None:
        include_inactive = self.query_one("#enrollments-show-inactive", Checkbox).value
        project = self._selected_project_filter

        def factory():
            if project is None:
                return self.core.gateway.list_all_enrollments(include_inactive)
            return self.core.gateway.list_enrollments(project, include_inactive)

        self.call_gateway(factory, self._fill_table, group="enrollments-load")

    @property
    def _selected_project_filter(self) -> str | None:
        value = self.query_one("#enrollments-project-select", Select).value
        if value is Select.BLANK or value == ALL_PROJECTS:
            return None
        return str(value)

    def _fill_table(self, rows: list[EnrollmentRow]) -> None:
        self.query_one("#enrollments-table", RefreshableTable).set_data(
            COLUMNS,
            [
                (
                    row.username,
                    row.project,
                    row.role,
                    "yes" if row.active else "no",
                    row.forwarded_port,
                )
                for row in rows
            ],
            [f"{row.username}@{row.project}" for row in rows],
        )

    @property
    def _selected_enrollment(self) -> tuple[str, str] | None:
        key = self.query_one("#enrollments-table", RefreshableTable).selected_key
        if key is None or "@" not in key:
            return None
        username, _, project = key.partition("@")
        return username, project

    @on(Select.Changed, "#enrollments-project-select")
    def _project_filter_changed(self) -> None:
        self.core.selected_project = self._selected_project_filter
        self._load_enrollments()

    @on(Checkbox.Changed, "#enrollments-show-inactive")
    def _filter_changed(self) -> None:
        self._load_enrollments()

    @on(Button.Pressed, "#enrollments-enroll-btn")
    def _enroll(self) -> None:
        self.app.push_screen(
            EnrollDialog(preselected_project=self._selected_project_filter),
            self._handle_enroll,
        )

    def _handle_enroll(self, result: tuple[str, str] | None) -> None:
        if result is None:
            return
        username, project = result
        self.call_gateway(
            lambda: self.core.gateway.enroll_user(username, project),
            lambda row: self._mutation_done(
                f"Enrolled `{row.username}` in `{row.project}` (port {row.forwarded_port})."
            ),
            group="enrollments-mutate",
        )

    @on(Button.Pressed, "#enrollments-cancel-btn")
    def _cancel_enrollment(self) -> None:
        selected = self._selected_enrollment
        if selected is None:
            self.notify("Select an enrollment first.", severity="warning")
            return
        username, project = selected
        self.app.push_screen(
            ConfirmDialog(
                f"Cancel enrollment of `{username}` in `{project}`?",
                "Stops and removes the user's cluster for this project.",
                confirm_label="Cancel enrollment",
            ),
            lambda confirmed: self._do_cancel(username, project) if confirmed else None,
        )

    def _do_cancel(self, username: str, project: str) -> None:
        self.call_gateway(
            lambda: self.core.gateway.cancel_enrollment(username, project),
            lambda _: self._mutation_done(f"Enrollment of `{username}` in `{project}` cancelled."),
            group="enrollments-mutate",
        )

    def _mutation_done(self, message: str) -> None:
        self.notify(message)
        self._load_enrollments()
