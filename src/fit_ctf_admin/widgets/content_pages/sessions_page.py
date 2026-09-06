"""User activity page: rendezvous logins, instance start/stop, best-effort SSH."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Label, Select, Static

from fit_ctf_admin.dto import ProjectRow, SessionRow, UserRow
from fit_ctf_admin.widgets.core_widget import AdminPage
from fit_ctf_admin.widgets.refreshable_table import RefreshableTable

COLUMNS = ("User", "Kind", "State", "Timestamp", "Detail")

SSH_NOTE = (
    "SSH activity is best-effort: parsed from the login-node container logs, "
    "available only while the user's cluster is running."
)


class SessionsPage(AdminPage):
    def compose(self) -> ComposeResult:
        yield Label("Sessions & activity", classes="page-title")
        with Horizontal(classes="page-toolbar"):
            yield Select([], prompt="User", id="sessions-user-select")
            yield Select([], prompt="Project", id="sessions-project-select")
            yield Button("User sessions", variant="primary", id="sessions-user-btn")
            yield Button("Project sessions", id="sessions-project-btn")
            yield Button("SSH activity", id="sessions-ssh-btn")
        yield Static(SSH_NOTE, id="sessions-note")
        yield RefreshableTable(id="sessions-table")

    def refresh_page(self) -> None:
        self.call_gateway(
            lambda: self.core.gateway.list_users(include_inactive=True),
            self._fill_users,
            group="sessions-users",
        )
        self.call_gateway(
            lambda: self.core.gateway.list_projects(),
            self._fill_projects,
            group="sessions-projects",
        )

    def _fill_users(self, users: list[UserRow]) -> None:
        select = self.query_one("#sessions-user-select", Select)
        current = select.value
        select.set_options((user.username, user.username) for user in users)
        if current is not Select.BLANK and any(u.username == current for u in users):
            select.value = current

    def _fill_projects(self, projects: list[ProjectRow]) -> None:
        select = self.query_one("#sessions-project-select", Select)
        current = select.value
        select.set_options((p.name, p.name) for p in projects)
        if current is not Select.BLANK and any(p.name == current for p in projects):
            select.value = current

    @property
    def _user(self) -> str | None:
        value = self.query_one("#sessions-user-select", Select).value
        return None if value is Select.BLANK else str(value)

    @property
    def _project(self) -> str | None:
        value = self.query_one("#sessions-project-select", Select).value
        return None if value is Select.BLANK else str(value)

    @on(Button.Pressed, "#sessions-user-btn")
    def _user_sessions(self) -> None:
        username = self._user
        if username is None:
            self.notify("Pick a user first.", severity="warning")
            return
        self.call_gateway(
            lambda: self.core.gateway.user_sessions(username),
            self._fill_table,
            group="sessions-load",
        )

    @on(Button.Pressed, "#sessions-project-btn")
    def _project_sessions(self) -> None:
        project = self._project
        if project is None:
            self.notify("Pick a project first.", severity="warning")
            return
        self.call_gateway(
            lambda: self.core.gateway.project_sessions(project),
            self._fill_table,
            group="sessions-load",
        )

    @on(Button.Pressed, "#sessions-ssh-btn")
    def _ssh_activity(self) -> None:
        username, project = self._user, self._project
        if username is None or project is None:
            self.notify("Pick both a user and a project.", severity="warning")
            return
        self.notify("Fetching SSH activity from container logs…", timeout=3)
        self.call_gateway(
            lambda: self.core.gateway.ssh_activity(username, project),
            self._fill_table,
            group="sessions-load",
        )

    def _fill_table(self, rows: list[SessionRow]) -> None:
        self.query_one("#sessions-table", RefreshableTable).set_data(
            COLUMNS,
            [(row.username, row.kind, row.state, row.timestamp or "—", row.detail) for row in rows],
            [str(index) for index in range(len(rows))],
        )
        if not rows:
            self.notify("No activity records found.", timeout=3)
