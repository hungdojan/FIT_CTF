"""Container/pod log viewer for project and user clusters."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Input, Label, Log, Select

from fit_ctf_admin.dto import EnrollmentRow, ProjectRow
from fit_ctf_admin.widgets.core_widget import AdminPage

KIND_OPTIONS = [("Project cluster", "project"), ("User cluster", "user")]


class LogsPage(AdminPage):
    def compose(self) -> ComposeResult:
        yield Label("Cluster logs", classes="page-title")
        with Horizontal(classes="page-toolbar"):
            yield Select(KIND_OPTIONS, value="project", allow_blank=False, id="logs-kind-select")
            yield Select([], prompt="Project", id="logs-project-select")
            yield Select([], prompt="User", id="logs-user-select", disabled=True)
            yield Input(value="500", placeholder="tail", type="integer", id="logs-tail-input")
            yield Button("Load logs", variant="primary", id="logs-load-btn")
        yield Log(id="logs-output", highlight=True)

    def refresh_page(self) -> None:
        self.call_gateway(
            lambda: self.core.gateway.list_projects(),
            self._fill_projects,
            group="logs-projects",
        )

    def _fill_projects(self, projects: list[ProjectRow]) -> None:
        select = self.query_one("#logs-project-select", Select)
        current = select.value
        select.set_options((p.name, p.name) for p in projects)
        if current is not Select.BLANK and any(p.name == current for p in projects):
            select.value = current

    @on(Select.Changed, "#logs-kind-select")
    def _kind_changed(self, event: Select.Changed) -> None:
        user_select = self.query_one("#logs-user-select", Select)
        user_select.disabled = event.value != "user"
        if event.value == "user":
            self._load_users()

    @on(Select.Changed, "#logs-project-select")
    def _project_changed(self) -> None:
        if str(self.query_one("#logs-kind-select", Select).value) == "user":
            self._load_users()

    def _load_users(self) -> None:
        project = self.query_one("#logs-project-select", Select).value
        if project is Select.BLANK:
            return
        self.call_gateway(
            lambda: self.core.gateway.list_enrollments(str(project)),
            self._fill_users,
            group="logs-users",
        )

    def _fill_users(self, rows: list[EnrollmentRow]) -> None:
        select = self.query_one("#logs-user-select", Select)
        current = select.value
        select.set_options((row.username, row.username) for row in rows)
        if current is not Select.BLANK and any(row.username == current for row in rows):
            select.value = current

    @property
    def _tail(self) -> int:
        text = self.query_one("#logs-tail-input", Input).value.strip()
        try:
            return max(1, int(text))
        except ValueError:
            return 500

    @on(Button.Pressed, "#logs-load-btn")
    def _load_logs(self) -> None:
        kind = str(self.query_one("#logs-kind-select", Select).value)
        project = self.query_one("#logs-project-select", Select).value
        if project is Select.BLANK:
            self.notify("Pick a project first.", severity="warning")
            return
        if kind == "user":
            username = self.query_one("#logs-user-select", Select).value
            if username is Select.BLANK:
                self.notify("Pick a user first.", severity="warning")
                return
            user = str(username)

            def factory():
                return self.core.gateway.user_cluster_logs(user, str(project), self._tail)
        else:

            def factory():
                return self.core.gateway.project_cluster_logs(str(project), self._tail)

        self.notify("Fetching logs…", timeout=2)
        self.call_gateway(factory, self._show_logs, group="logs-load")

    def _show_logs(self, text: str) -> None:
        log = self.query_one("#logs-output", Log)
        log.clear()
        log.write(text or "(no log output — is the cluster running?)")
