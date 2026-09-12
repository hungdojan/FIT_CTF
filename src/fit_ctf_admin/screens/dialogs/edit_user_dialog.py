"""Modal form for editing an existing user (email, role, password).

Like :class:`~fit_ctf_admin.screens.dialogs.new_user_dialog.NewUserDialog`, the
dialog owns the gateway calls so a rejected value keeps the form open. The
password is only touched when a new one is typed or generation is requested.
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
)


@dataclass(frozen=True, slots=True)
class EditUserRequest:
    username: str
    email: str
    role: UserRole
    password: str | None
    generate_password: bool

    @property
    def changes_password(self) -> bool:
        return self.generate_password or bool(self.password)


@dataclass(frozen=True, slots=True)
class EditUserResult:
    username: str
    password: str | None
    """Plaintext password when it was changed, so the page can reveal it once."""


SubmitCallback = Callable[[EditUserRequest], Awaitable[str | None]]


class EditUserDialog(ModalScreen[EditUserResult | None]):
    """Dismisses with :class:`EditUserResult` once the update succeeded."""

    DEFAULT_CSS = """
    EditUserDialog {
        align: center middle;
    }
    EditUserDialog > Vertical {
        width: 64;
        height: auto;
        padding: 1 2;
        border: heavy $primary;
        background: $surface;
    }
    EditUserDialog .dialog-title {
        text-style: bold;
        margin-bottom: 1;
    }
    EditUserDialog .field-label {
        color: $text-muted;
    }
    EditUserDialog Input, EditUserDialog Select, EditUserDialog Checkbox {
        margin-bottom: 1;
    }
    EditUserDialog PasswordField {
        margin-bottom: 1;
    }
    EditUserDialog PasswordField Input {
        margin-bottom: 0;
    }
    EditUserDialog #edit-user-buttons {
        height: auto;
        align-horizontal: right;
    }
    EditUserDialog #edit-user-buttons Button {
        margin-left: 2;
    }
    """

    BINDINGS = [("escape", "dismiss(None)", "Cancel")]

    def __init__(self, row: UserRow, submit: SubmitCallback) -> None:
        super().__init__()
        self._row = row
        self._submit = submit

    def compose(self) -> ComposeResult:
        role = next((r for r in UserRole if r.value == self._row.role), UserRole.USER)
        with Vertical():
            yield Label(f"Edit user `{self._row.username}`", classes="dialog-title")
            yield Label("Email", classes="field-label")
            yield Input(
                value=self._row.email,
                placeholder="user@example.com",
                id="edit-user-email",
                validators=email_validators(),
                valid_empty=True,
                validate_on=["blur", "submitted"],
            )
            yield FieldError("", id="edit-user-email-error")
            yield Label("Role", classes="field-label")
            yield Select(
                [(option.value, option) for option in UserRole],
                value=role,
                id="edit-user-role",
            )
            yield Label("New password (leave empty to keep the current one)", classes="field-label")
            yield PasswordField("edit-user-password", placeholder="New password")
            yield Checkbox("Generate a new password", id="edit-user-generate")
            with Horizontal(id="edit-user-buttons"):
                yield Button("Cancel", id="edit-user-cancel-btn")
                yield Button("Save", variant="primary", id="edit-user-save-btn")

    # -- inline validation ----------------------------------------------------

    @on(Input.Changed, "#edit-user-email")
    def _clear_error(self, event: Input.Changed) -> None:
        self.query_one("#edit-user-email-error", FieldError).clear()

    @on(Input.Blurred, "#edit-user-email")
    def _show_error(self, event: Input.Blurred) -> None:
        error = self.query_one("#edit-user-email-error", FieldError)
        result = event.validation_result
        if result is not None and not result.is_valid:
            error.show(result.failure_descriptions[0])
        else:
            error.clear()

    @on(Input.Blurred, "#edit-user-password")
    def _show_password_error(self, event: Input.Blurred) -> None:
        field = self.query_one(PasswordField)
        result = event.validation_result
        if result is not None and not result.is_valid:
            field.error.show(result.failure_descriptions[0])
        else:
            field.error.clear()

    @on(Checkbox.Changed, "#edit-user-generate")
    def _toggle_password_input(self, event: Checkbox.Changed) -> None:
        self.query_one(PasswordField).set_disabled(event.value)

    # -- submit ----------------------------------------------------------------

    def _collect(self) -> EditUserRequest | None:
        generate_password = self.query_one("#edit-user-generate", Checkbox).value
        password_field = self.query_one(PasswordField)
        fields = [self.query_one("#edit-user-email", Input)]
        if not generate_password and password_field.value:
            fields.append(password_field.input)
        failure = first_failure(fields)
        if failure is not None:
            field, message = failure
            if field.id == "edit-user-password":
                password_field.error.show(message)
            else:
                self.query_one("#edit-user-email-error", FieldError).show(message)
            self.notify(message, severity="error")
            field.focus()
            return None

        role = self.query_one("#edit-user-role", Select).value
        return EditUserRequest(
            username=self._row.username,
            email=self.query_one("#edit-user-email", Input).value.strip(),
            role=role if isinstance(role, UserRole) else UserRole.USER,
            password=password_field.value or None,
            generate_password=generate_password,
        )

    @on(Button.Pressed, "#edit-user-save-btn")
    def _save(self) -> None:
        request = self._collect()
        if request is None:
            return
        self.run_worker(partial(self._do_save, request), exclusive=True, exit_on_error=False)

    async def _do_save(self, request: EditUserRequest) -> None:
        save_btn = self.query_one("#edit-user-save-btn", Button)
        save_btn.disabled = True
        try:
            ok, password = await run_guarded(self, partial(self._submit, request))
        finally:
            save_btn.disabled = False
        if ok:  # the form stays open (with its values) on failure
            self.dismiss(EditUserResult(username=request.username, password=password))

    @on(Button.Pressed, "#edit-user-cancel-btn")
    def _cancel(self) -> None:
        self.dismiss(None)
