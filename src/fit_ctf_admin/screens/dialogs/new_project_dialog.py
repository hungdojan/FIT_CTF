"""Modal form for creating a project."""

from __future__ import annotations

from dataclasses import dataclass

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label


@dataclass(frozen=True, slots=True)
class NewProjectRequest:
    name: str
    max_nof_users: int
    starting_port_bind: int
    description: str


class NewProjectDialog(ModalScreen[NewProjectRequest | None]):
    DEFAULT_CSS = """
    NewProjectDialog {
        align: center middle;
    }
    NewProjectDialog > Vertical {
        width: 64;
        height: auto;
        padding: 1 2;
        border: heavy $primary;
        background: $surface;
    }
    NewProjectDialog .dialog-title {
        text-style: bold;
        margin-bottom: 1;
    }
    NewProjectDialog Input {
        margin-bottom: 1;
    }
    NewProjectDialog Horizontal {
        height: auto;
        align-horizontal: right;
    }
    NewProjectDialog Horizontal Button {
        margin-left: 2;
    }
    """

    BINDINGS = [("escape", "dismiss(None)", "Cancel")]

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("New project", classes="dialog-title")
            yield Input(placeholder="Project name (lowercase slug)", id="new-project-name")
            yield Input(
                placeholder="Capacity (max users)",
                type="integer",
                id="new-project-capacity",
            )
            yield Input(
                placeholder="Starting port (empty = auto)",
                type="integer",
                id="new-project-port",
            )
            yield Input(placeholder="Description (optional)", id="new-project-description")
            with Horizontal():
                yield Button("Cancel", id="new-project-cancel-btn")
                yield Button("Create", variant="primary", id="new-project-create-btn")

    @on(Button.Pressed, "#new-project-create-btn")
    def _create(self) -> None:
        capacity_text = self.query_one("#new-project-capacity", Input).value.strip()
        port_text = self.query_one("#new-project-port", Input).value.strip()
        self.dismiss(
            NewProjectRequest(
                name=self.query_one("#new-project-name", Input).value,
                max_nof_users=int(capacity_text) if capacity_text else 0,
                starting_port_bind=int(port_text) if port_text else -1,
                description=self.query_one("#new-project-description", Input).value,
            )
        )

    @on(Button.Pressed, "#new-project-cancel-btn")
    def _cancel(self) -> None:
        self.dismiss(None)
