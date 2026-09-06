"""Modal form for enrolling a user into a project.

The user picker is populated from ``enrollable_users`` for the chosen project,
so only valid candidates can be selected (no free-text usernames).
"""

from __future__ import annotations

from functools import partial

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Select

from fit_ctf_admin.constants import ERROR_NOTIFY_TIMEOUT
from fit_ctf_admin.core.admin_core import AdminCore
from fit_ctf_admin.exceptions import AdminError


class EnrollDialog(ModalScreen[tuple[str, str] | None]):
    """Dismisses with ``(username, project_name)`` or ``None``."""

    DEFAULT_CSS = """
    EnrollDialog {
        align: center middle;
    }
    EnrollDialog > Vertical {
        width: 64;
        height: auto;
        padding: 1 2;
        border: heavy $primary;
        background: $surface;
    }
    EnrollDialog .dialog-title {
        text-style: bold;
        margin-bottom: 1;
    }
    EnrollDialog Select {
        margin-bottom: 1;
    }
    EnrollDialog Horizontal {
        height: auto;
        align-horizontal: right;
    }
    EnrollDialog Horizontal Button {
        margin-left: 2;
    }
    """

    BINDINGS = [("escape", "dismiss(None)", "Cancel")]

    def __init__(self, preselected_project: str | None = None) -> None:
        super().__init__()
        self._preselected_project = preselected_project

    @property
    def core(self) -> AdminCore:
        return self.app.admin_core  # type: ignore[attr-defined]

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Enroll user", classes="dialog-title")
            yield Select([], prompt="Project", id="enroll-project-select")
            yield Select([], prompt="User", id="enroll-user-select", disabled=True)
            with Horizontal():
                yield Button("Cancel", id="enroll-cancel-btn")
                yield Button("Enroll", variant="primary", id="enroll-ok-btn")

    def on_mount(self) -> None:
        self.run_worker(self._load_projects, exclusive=True, exit_on_error=False)

    async def _load_projects(self) -> None:
        try:
            projects = await self.core.gateway.list_projects()
        except AdminError as exc:
            self.notify(str(exc), severity="error", timeout=ERROR_NOTIFY_TIMEOUT)
            return
        select = self.query_one("#enroll-project-select", Select)
        select.set_options((p.name, p.name) for p in projects)
        if self._preselected_project and any(p.name == self._preselected_project for p in projects):
            select.value = self._preselected_project

    @on(Select.Changed, "#enroll-project-select")
    def _project_changed(self, event: Select.Changed) -> None:
        user_select = self.query_one("#enroll-user-select", Select)
        if event.value is Select.BLANK:
            user_select.set_options([])
            user_select.disabled = True
            return
        self.run_worker(
            partial(self._load_users, str(event.value)), exclusive=True, exit_on_error=False
        )

    async def _load_users(self, project_name: str) -> None:
        try:
            usernames = await self.core.gateway.enrollable_users(project_name)
        except AdminError as exc:
            self.notify(str(exc), severity="error", timeout=ERROR_NOTIFY_TIMEOUT)
            return
        user_select = self.query_one("#enroll-user-select", Select)
        user_select.set_options((name, name) for name in usernames)
        user_select.disabled = False

    @on(Button.Pressed, "#enroll-ok-btn")
    def _enroll(self) -> None:
        project = self.query_one("#enroll-project-select", Select).value
        user = self.query_one("#enroll-user-select", Select).value
        if project is Select.BLANK or user is Select.BLANK:
            self.notify("Select both a project and a user.", severity="warning")
            return
        self.dismiss((str(user), str(project)))

    @on(Button.Pressed, "#enroll-cancel-btn")
    def _cancel(self) -> None:
        self.dismiss(None)
