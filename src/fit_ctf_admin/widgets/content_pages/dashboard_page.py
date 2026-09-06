"""Landing page: backend mode, entity counts, and a project overview table."""

from __future__ import annotations

from dataclasses import dataclass

from textual.app import ComposeResult
from textual.widgets import Label, Static

from fit_ctf_admin.dto import ClusterRow, ProjectRow
from fit_ctf_admin.widgets.core_widget import AdminPage
from fit_ctf_admin.widgets.refreshable_table import RefreshableTable

OVERVIEW_COLUMNS = ("Project", "Enrolled / capacity", "Cluster running", "Scenarios")


@dataclass(frozen=True, slots=True)
class _DashboardData:
    users: int
    projects: int
    enrollments: int
    scenarios: int
    modules: int
    project_rows: list[ProjectRow]
    cluster_rows: list[ClusterRow]


class DashboardPage(AdminPage):
    def compose(self) -> ComposeResult:
        yield Label("Dashboard", classes="page-title")
        yield Static(self.core.mode_label, id="dashboard-mode")
        yield Static("Loading…", id="dashboard-counts")
        yield Label("Projects overview")
        yield RefreshableTable(id="dashboard-projects-table")

    def on_mount(self) -> None:
        self.refresh_page()

    def refresh_page(self) -> None:
        self.call_gateway(lambda: self._load(), self._show, group="dashboard")

    async def _load(self) -> _DashboardData:
        gateway = self.core.gateway
        return _DashboardData(
            users=len(await gateway.list_users(include_inactive=True)),
            projects=len(await gateway.list_projects(include_inactive=True)),
            enrollments=len(await gateway.list_all_enrollments(include_inactive=True)),
            scenarios=len(await gateway.list_scenarios()),
            modules=len(await gateway.list_modules()),
            project_rows=await gateway.list_projects(),
            cluster_rows=await gateway.list_project_clusters(),
        )

    def _show(self, data: _DashboardData) -> None:
        self.query_one("#dashboard-counts", Static).update(
            f"Users: {data.users}    Projects: {data.projects}    "
            f"Enrollments: {data.enrollments}    Scenarios: {data.scenarios}    "
            f"Modules: {data.modules}"
        )
        clusters = {row.project: row for row in data.cluster_rows}
        rows = []
        for project in data.project_rows:
            cluster = clusters.get(project.name)
            rows.append(
                (
                    project.name,
                    f"{project.active_users} / {project.max_nof_users}",
                    "yes" if cluster is not None and cluster.running else "no",
                    ", ".join(cluster.scenarios) if cluster and cluster.scenarios else "—",
                )
            )
        self.query_one("#dashboard-projects-table", RefreshableTable).set_data(
            OVERVIEW_COLUMNS, rows, [project.name for project in data.project_rows]
        )
