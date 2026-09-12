"""Modal form for creating a user.

The dialog owns the create call: fields are validated locally first and a failing
gateway call only raises a notification, so a rejected username or a weak password
never costs the operator the whole form.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from typing import Awaitable, Callable

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, Select

from fit_ctf.components.types import UserRole
from fit_ctf_admin.dto import UserRow
from fit_ctf_admin.screens.dialogs.form_support import (
    FieldError,
    PasswordField,
    email_validators,
    first_failure,
    run_guarded,
    username_validators,
)


@dataclass(frozen=True, slots=True)
class NewUserRequest:
    username: str
    email: str
    role: UserRole
    password: str | None
    generate_password: bool


CreatedUser = tuple[UserRow, str]
SubmitCallback = Callable[[NewUserRequest], Awaitable[CreatedUser]]


class NewUserDialog(ModalScreen[CreatedUser | None]):
    """Dismisses with ``(row, plaintext password)`` once creation succeeded."""

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
    NewUserDialog .field-label {
        color: $text-muted;
    }
    NewUserDialog Input, NewUserDialog Select, NewUserDialog Checkbox {
        margin-bottom: 1;
    }
    NewUserDialog PasswordField {
        margin-bottom: 1;
    }
    NewUserDialog PasswordField Input {
        margin-bottom: 0;
    }
    NewUserDialog #new-user-buttons {
        height: auto;
        align-horizontal: right;
    }
    NewUserDialog #new-user-buttons Button {
        margin-left: 2;
    }
    """

    BINDINGS = [("escape", "dismiss(None)", "Cancel")]

    def __init__(self, submit: SubmitCallback) -> None:
        super().__init__()
        self._submit = submit

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("New user", classes="dialog-title")
            yield Label("Username", classes="field-label")
            yield Input(
                placeholder="Username",
                id="new-user-username",
                validators=username_validators(),
                validate_on=["blur", "submitted"],
            )
            yield FieldError("", id="new-user-username-error")
            yield Label("Email (optional)", classes="field-label")
            yield Input(
                placeholder="user@example.com",
                id="new-user-email",
                validators=email_validators(),
                valid_empty=True,
                validate_on=["blur", "submitted"],
            )
            yield FieldError("", id="new-user-email-error")
            yield Label("Role", classes="field-label")
            yield Select(
                [(role.value, role) for role in UserRole],
                value=UserRole.USER,
                id="new-user-role",
            )
            yield Label("Password", classes="field-label")
            yield PasswordField("new-user-password", id="new-user-password-field")
            yield Checkbox("Generate password", id="new-user-generate")
            with Horizontal(id="new-user-buttons"):
                yield Button("Cancel", id="new-user-cancel-btn")
                yield Button("Create", variant="primary", id="new-user-create-btn")

    # -- inline validation ----------------------------------------------------

    @on(Input.Changed, "#new-user-username")
    @on(Input.Changed, "#new-user-email")
    def _clear_error(self, event: Input.Changed) -> None:
        self.query_one(f"#{event.input.id}-error", FieldError).clear()

    @on(Input.Blurred, "#new-user-username")
    @on(Input.Blurred, "#new-user-email")
    def _show_error(self, event: Input.Blurred) -> None:
        error = self.query_one(f"#{event.input.id}-error", FieldError)
        result = event.validation_result
        if result is not None and not result.is_valid:
            error.show(result.failure_descriptions[0])
        else:
            error.clear()

    @on(Input.Blurred, "#new-user-password")
    def _show_password_error(self, event: Input.Blurred) -> None:
        field = self.query_one("#new-user-password-field", PasswordField)
        result = event.validation_result
        if result is not None and not result.is_valid:
            field.error.show(result.failure_descriptions[0])
        else:
            field.error.clear()

    @on(Checkbox.Changed, "#new-user-generate")
    def _toggle_password_input(self, event: Checkbox.Changed) -> None:
        self.query_one("#new-user-password-field", PasswordField).set_disabled(event.value)

    # -- submit ----------------------------------------------------------------

    def _collect(self) -> NewUserRequest | None:
        """Validate the form; show the first problem and return ``None`` if invalid."""
        generate_password = self.query_one("#new-user-generate", Checkbox).value
        password_field = self.query_one("#new-user-password-field", PasswordField)
        fields = [
            self.query_one("#new-user-username", Input),
            self.query_one("#new-user-email", Input),
        ]
        if not generate_password:
            fields.append(password_field.input)
        failure = first_failure(fields)
        if failure is not None:
            field, message = failure
            if field.id == "new-user-password":
                password_field.error.show(message)
            else:
                self.query_one(f"#{field.id}-error", FieldError).show(message)
            self.notify(message, severity="error")
            field.focus()
            return None

        password = password_field.value
        if not generate_password and not password:
            message = "Enter a password or enable password generation."
            password_field.error.show(message)
            self.notify(message, severity="error")
            password_field.input.focus()
            return None

        role = self.query_one("#new-user-role", Select).value
        return NewUserRequest(
            username=self.query_one("#new-user-username", Input).value.strip(),
            email=self.query_one("#new-user-email", Input).value.strip(),
            role=role if isinstance(role, UserRole) else UserRole.USER,
            password=password or None,
            generate_password=generate_password,
        )

    @on(Button.Pressed, "#new-user-create-btn")
    def _create(self) -> None:
        request = self._collect()
        if request is None:
            return
        self.run_worker(partial(self._do_create, request), exclusive=True, exit_on_error=False)

    async def _do_create(self, request: NewUserRequest) -> None:
        create_btn = self.query_one("#new-user-create-btn", Button)
        create_btn.disabled = True
        try:
            ok, result = await run_guarded(self, partial(self._submit, request))
        finally:
            create_btn.disabled = False
        if ok:  # the form stays open (with its values) on failure
            self.dismiss(result)

    @on(Button.Pressed, "#new-user-cancel-btn")
    def _cancel(self) -> None:
        self.dismiss(None)
