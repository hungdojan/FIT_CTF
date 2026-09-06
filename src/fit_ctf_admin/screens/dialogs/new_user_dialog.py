"""Modal form for creating a user."""

from __future__ import annotations

from dataclasses import dataclass

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, Select

from fit_ctf.components.types import UserRole


@dataclass(frozen=True, slots=True)
class NewUserRequest:
    username: str
    email: str
    role: UserRole
    password: str | None
    generate_password: bool


class NewUserDialog(ModalScreen[NewUserRequest | None]):
    DEFAULT_CSS = """
    NewUserDialog {
        align: center middle;
    }
    NewUserDialog > Vertical {
        width: 64;
        height: auto;
        padding: 1 2;
        border: heavy $primary;
        background: $surface;
    }
    NewUserDialog .dialog-title {
        text-style: bold;
        margin-bottom: 1;
    }
    NewUserDialog Input, NewUserDialog Select, NewUserDialog Checkbox {
        margin-bottom: 1;
    }
    NewUserDialog Horizontal {
        height: auto;
        align-horizontal: right;
    }
    NewUserDialog Horizontal Button {
        margin-left: 2;
    }
    """

    BINDINGS = [("escape", "dismiss(None)", "Cancel")]

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("New user", classes="dialog-title")
            yield Input(placeholder="Username", id="new-user-username")
            yield Input(placeholder="Email (optional)", id="new-user-email")
            yield Select(
                [(role.value, role) for role in UserRole],
                value=UserRole.USER,
                id="new-user-role",
            )
            yield Input(placeholder="Password", password=True, id="new-user-password")
            yield Checkbox("Generate password", id="new-user-generate")
            with Horizontal():
                yield Button("Cancel", id="new-user-cancel-btn")
                yield Button("Create", variant="primary", id="new-user-create-btn")

    @on(Checkbox.Changed, "#new-user-generate")
    def _toggle_password_input(self, event: Checkbox.Changed) -> None:
        self.query_one("#new-user-password", Input).disabled = event.value

    @on(Button.Pressed, "#new-user-create-btn")
    def _create(self) -> None:
        role = self.query_one("#new-user-role", Select).value
        password = self.query_one("#new-user-password", Input).value
        self.dismiss(
            NewUserRequest(
                username=self.query_one("#new-user-username", Input).value,
                email=self.query_one("#new-user-email", Input).value,
                role=role if isinstance(role, UserRole) else UserRole.USER,
                password=password or None,
                generate_password=self.query_one("#new-user-generate", Checkbox).value,
            )
        )

    @on(Button.Pressed, "#new-user-cancel-btn")
    def _cancel(self) -> None:
        self.dismiss(None)
