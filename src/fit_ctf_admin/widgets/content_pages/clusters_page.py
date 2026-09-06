"""Cluster lifecycle & health page: project clusters and per-project user clusters."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Label, Select

from fit_ctf_admin.dto import ClusterRow, HealthRow
from fit_ctf_admin.screens.dialogs.confirm_dialog import ConfirmDialog
from fit_ctf_admin.screens.dialogs.table_dialog import TableDialog
from fit_ctf_admin.widgets.core_widget import AdminPage
from fit_ctf_admin.widgets.refreshable_table import RefreshableTable

PROJECT_COLUMNS = ("Project", "Cluster", "Running", "Scenarios")
USER_COLUMNS = ("User", "Cluster", "Running", "Scenarios")
POLL_INTERVAL = 5.0


def _cluster_cells(row: ClusterRow) -> tuple:
    first = row.project if row.kind == "project" else (row.username or "")
    return (
        first,
        row.name or "(missing)",
        "yes" if row.running else "no",
        ", ".join(row.scenarios) or "—",
    )


class ClustersPage(AdminPage):
    def compose(self) -> ComposeResult:
        yield Label("Clusters", classes="page-title")
        yield Label("Project clusters")
        with Horizontal(classes="page-toolbar"):
            yield Button("Start", variant="success", id="pc-start-btn")
            yield Button("Stop", id="pc-stop-btn")
            yield Button("Restart", id="pc-restart-btn")
            yield Button("Health", id="pc-health-btn")
        yield RefreshableTable(id="project-clusters-table")
        yield Label("User clusters")
        with Horizontal(classes="page-toolbar"):
            yield Select([], prompt="Project", id="uc-project-select")
            yield Button("Start", variant="success", id="uc-start-btn")
            yield Button("Stop", id="uc-stop-btn")
            yield Button("Restart", id="uc-restart-btn")
            yield Button("Health", id="uc-health-btn")
            yield Button("Stop all", variant="error", id="uc-stop-all-btn")
        yield RefreshableTable(id="user-clusters-table")

    def on_mount(self) -> None:
        self._poll_timer = self.set_interval(POLL_INTERVAL, self.refresh_page, pause=True)

    def on_show(self) -> None:
        self._poll_timer.resume()
        self.refresh_page()

    def on_hide(self) -> None:
        self._poll_timer.pause()

    def refresh_page(self) -> None:
        self.call_gateway(
            lambda: self.core.gateway.list_project_clusters(),
            self._fill_project_clusters,
            group="clusters-project-load",
        )
        self._load_user_clusters()

    # -- project clusters --------------------------------------------------

    def _fill_project_clusters(self, rows: list[ClusterRow]) -> None:
        self.query_one("#project-clusters-table", RefreshableTable).set_data(
            PROJECT_COLUMNS,
            [_cluster_cells(row) for row in rows],
            [row.project for row in rows],
        )
        select = self.query_one("#uc-project-select", Select)
        current = select.value
        select.set_options((row.project, row.project) for row in rows)
        if current is not Select.BLANK and any(row.project == current for row in rows):
            select.value = current

    @property
    def _selected_project_cluster(self) -> str | None:
        return self.query_one("#project-clusters-table", RefreshableTable).selected_key

    @on(Button.Pressed, "#pc-start-btn")
    def _start_project(self) -> None:
        self._project_action("start")

    @on(Button.Pressed, "#pc-stop-btn")
    def _stop_project(self) -> None:
        self._project_action("stop")

    @on(Button.Pressed, "#pc-restart-btn")
    def _restart_project(self) -> None:
        self._project_action("restart")

    def _project_action(self, action: str) -> None:
        project = self._selected_project_cluster
        if project is None:
            self.notify("Select a project cluster first.", severity="warning")
            return
        gateway = self.core.gateway
        awaitable = {
            "start": gateway.start_project_cluster,
            "stop": gateway.stop_project_cluster,
            "restart": gateway.restart_project_cluster,
        }[action](project)
        self._run_lifecycle(awaitable, f"Project cluster `{project}`: {action} finished.")

    @on(Button.Pressed, "#pc-health-btn")
    def _project_health(self) -> None:
        project = self._selected_project_cluster
        if project is None:
            self.notify("Select a project cluster first.", severity="warning")
            return
        self.call_gateway(
            lambda: self.core.gateway.project_cluster_health(project),
            lambda rows: self._show_health(f"Health of project cluster `{project}`", rows),
            group="clusters-health",
        )

    # -- user clusters -----------------------------------------------------

    @property
    def _user_cluster_project(self) -> str | None:
        value = self.query_one("#uc-project-select", Select).value
        return None if value is Select.BLANK else str(value)

    def _load_user_clusters(self) -> None:
        project = self._user_cluster_project
        table = self.query_one("#user-clusters-table", RefreshableTable)
        if project is None:
            table.set_data(USER_COLUMNS, [], [])
            return
        self.call_gateway(
            lambda: self.core.gateway.list_user_clusters(project),
            self._fill_user_clusters,
            group="clusters-user-load",
        )

    def _fill_user_clusters(self, rows: list[ClusterRow]) -> None:
        self.query_one("#user-clusters-table", RefreshableTable).set_data(
            USER_COLUMNS,
            [_cluster_cells(row) for row in rows],
            [row.username or "" for row in rows],
        )

    @property
    def _selected_user_cluster(self) -> tuple[str, str] | None:
        project = self._user_cluster_project
        username = self.query_one("#user-clusters-table", RefreshableTable).selected_key
        if project is None or not username:
            return None
        return username, project

    @on(Select.Changed, "#uc-project-select")
    def _user_project_changed(self) -> None:
        self._load_user_clusters()

    @on(Button.Pressed, "#uc-start-btn")
    def _start_user(self) -> None:
        self._user_action("start")

    @on(Button.Pressed, "#uc-stop-btn")
    def _stop_user(self) -> None:
        self._user_action("stop")

    @on(Button.Pressed, "#uc-restart-btn")
    def _restart_user(self) -> None:
        self._user_action("restart")

    def _user_action(self, action: str) -> None:
        selected = self._selected_user_cluster
        if selected is None:
            self.notify("Select a user cluster first.", severity="warning")
            return
        username, project = selected
        gateway = self.core.gateway
        awaitable = {
            "start": gateway.start_user_cluster,
            "stop": gateway.stop_user_cluster,
            "restart": gateway.restart_user_cluster,
        }[action](username, project)
        self._run_lifecycle(
            awaitable, f"Cluster of `{username}` in `{project}`: {action} finished."
        )

    @on(Button.Pressed, "#uc-health-btn")
    def _user_health(self) -> None:
        selected = self._selected_user_cluster
        if selected is None:
            self.notify("Select a user cluster first.", severity="warning")
            return
        username, project = selected
        self.call_gateway(
            lambda: self.core.gateway.user_cluster_health(username, project),
            lambda rows: self._show_health(f"Health of `{username}` cluster in `{project}`", rows),
            group="clusters-health",
        )

    @on(Button.Pressed, "#uc-stop-all-btn")
    def _stop_all_users(self) -> None:
        project = self._user_cluster_project
        if project is None:
            self.notify("Select a project first.", severity="warning")
            return
        self.app.push_screen(
            ConfirmDialog(
                f"Stop all user clusters in `{project}`?",
                "Every participant of the project loses their running instance.",
                confirm_label="Stop all",
            ),
            lambda confirmed: self._do_stop_all(project) if confirmed else None,
        )

    def _do_stop_all(self, project: str) -> None:
        self._run_lifecycle(
            self.core.gateway.stop_all_user_clusters(project),
            f"All user clusters in `{project}` stopped.",
        )

    # -- helpers -------------------------------------------------------------

    def _run_lifecycle(self, awaitable, message: str) -> None:
        self.notify("Working…", timeout=2)
        self.call_gateway(
            lambda: awaitable,
            lambda _: self._lifecycle_done(message),
            group="clusters-lifecycle",
        )

    def _lifecycle_done(self, message: str) -> None:
        self.notify(message)
        self.refresh_page()

    def _show_health(self, title: str, rows: list[HealthRow]) -> None:
        self.app.push_screen(
            TableDialog(
                title,
                ("Container", "Image", "State"),
                [(row.name, row.image, row.state) for row in rows],
                empty_message="No containers found (cluster is probably not running).",
            )
        )
