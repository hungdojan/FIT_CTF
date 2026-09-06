"""Progress & leaderboard page with per-user drill-down."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Label, Select

from fit_ctf_admin.dto import (
    LeaderboardRow,
    ProjectRow,
    SolvedSecretRow,
    SubmissionRow,
)
from fit_ctf_admin.widgets.core_widget import AdminPage
from fit_ctf_admin.widgets.refreshable_table import RefreshableTable

LEADERBOARD_COLUMNS = ("#", "User", "Solved", "Total", "Score", "Last submit")
SOLVED_COLUMNS = ("Scenario", "Secret", "Submitted at", "Cluster")
SUBMISSION_COLUMNS = ("Submitted value", "Timestamp")


class ProgressPage(AdminPage):
    def compose(self) -> ComposeResult:
        yield Label("Progress & leaderboard", classes="page-title")
        with Horizontal(classes="page-toolbar"):
            yield Select([], prompt="Project", id="progress-project-select")
        yield RefreshableTable(id="leaderboard-table")
        yield Label("Selected user: solved secrets")
        yield RefreshableTable(id="solved-table")
        yield Label("Selected user: submission log")
        yield RefreshableTable(id="submissions-table")

    def refresh_page(self) -> None:
        self.call_gateway(
            lambda: self.core.gateway.list_projects(),
            self._fill_projects,
            group="progress-projects",
        )
        self._load_leaderboard()

    def _fill_projects(self, projects: list[ProjectRow]) -> None:
        select = self.query_one("#progress-project-select", Select)
        current = select.value
        select.set_options((p.name, p.name) for p in projects)
        if current is not Select.BLANK and any(p.name == current for p in projects):
            select.value = current

    @property
    def _project(self) -> str | None:
        value = self.query_one("#progress-project-select", Select).value
        return None if value is Select.BLANK else str(value)

    def _load_leaderboard(self) -> None:
        project = self._project
        if project is None:
            self.query_one("#leaderboard-table", RefreshableTable).set_data(
                LEADERBOARD_COLUMNS, [], []
            )
            return
        self.call_gateway(
            lambda: self.core.gateway.leaderboard(project),
            self._fill_leaderboard,
            group="progress-leaderboard",
        )

    def _fill_leaderboard(self, rows: list[LeaderboardRow]) -> None:
        self.query_one("#leaderboard-table", RefreshableTable).set_data(
            LEADERBOARD_COLUMNS,
            [
                (
                    row.position,
                    row.username,
                    row.found_secrets,
                    row.total_secrets,
                    row.percentage,
                    row.last_submit or "—",
                )
                for row in rows
            ],
            [row.username for row in rows],
        )

    @on(Select.Changed, "#progress-project-select")
    def _project_changed(self) -> None:
        self._load_leaderboard()

    @on(RefreshableTable.RowHighlighted, "#leaderboard-table")
    def _user_highlighted(self) -> None:
        project = self._project
        username = self.query_one("#leaderboard-table", RefreshableTable).selected_key
        if project is None or username is None:
            return
        self.call_gateway(
            lambda: self.core.gateway.solved_secrets(username, project),
            self._fill_solved,
            group="progress-solved",
        )
        self.call_gateway(
            lambda: self.core.gateway.submission_log(username, project),
            self._fill_submissions,
            group="progress-submissions",
        )

    def _fill_solved(self, rows: list[SolvedSecretRow]) -> None:
        self.query_one("#solved-table", RefreshableTable).set_data(
            SOLVED_COLUMNS,
            [(row.scenario, row.name, row.submitted_at, row.cluster_kind) for row in rows],
            [f"{row.scenario}/{row.name}" for row in rows],
        )

    def _fill_submissions(self, rows: list[SubmissionRow]) -> None:
        self.query_one("#submissions-table", RefreshableTable).set_data(
            SUBMISSION_COLUMNS,
            [(row.value, row.timestamp) for row in rows],
            [f"{index}" for index, _ in enumerate(rows)],
        )
