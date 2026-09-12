"""Shared pieces for the dialog forms: validators, inline errors, password fields.

Dialogs built on these keep themselves open when something goes wrong: fields are
validated locally (Textual validators) before the gateway is called, and gateway
failures are reported as notifications without dismissing the form.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Iterable

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.validation import Function, Regex, Validator
from textual.widgets import Button, Input, Label

from fit_ctf.components.auth.auth_interface import AuthInterface
from fit_ctf.exceptions import CTFBaseException
from fit_ctf_admin.constants import ERROR_NOTIFY_TIMEOUT
from fit_ctf_admin.exceptions import AdminError

# matches AuthInterface.validate_password_strength
PASSWORD_RULE = (
    "Password needs at least 8 characters, including a lower case letter, "
    "an upper case letter and a digit."
)


def username_validators() -> list[Validator]:
    return [Regex(r"^\S+$", failure_description="Username cannot be empty or contain spaces.")]


def email_validators() -> list[Validator]:
    return [
        Regex(
            r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
            failure_description="Email must look like user@example.com.",
        )
    ]


def password_validators() -> list[Validator]:
    """Mirror the backend rule (``resolve_new_password``) in the form itself."""
    return [Function(AuthInterface.validate_password_strength, PASSWORD_RULE)]


def friendly_error(exc: Exception) -> str:
    """One readable line out of a ``ValueError`` / pydantic ``ValidationError``.

    Pydantic's ``str(exc)`` is a multi-line dump ("1 validation error for … Value
    error, <the actual message>"); dialogs show the message alone.
    """
    errors = getattr(exc, "errors", None)
    if callable(errors):
        try:
            messages = [str(item.get("msg", "")) for item in errors()]
        except Exception:  # not a pydantic error after all
            messages = []
        for message in messages:
            if message:
                return message.removeprefix("Value error, ").removeprefix("Assertion failed, ")
    return str(exc)


def first_failure(fields: Iterable[Input]) -> tuple[Input, str] | None:
    """Return the first field that fails validation together with its message."""
    for field in fields:
        result = field.validate(field.value)
        if result is not None and not result.is_valid:
            description = result.failure_descriptions
            return field, description[0] if description else "Invalid value."
    return None


class FieldError(Label):
    """Inline error line under an input; empty (and invisible) when valid."""

    DEFAULT_CSS = """
    FieldError {
        color: $error;
        height: auto;
        display: none;
    }
    FieldError.-shown {
        display: block;
    }
    """

    def show(self, message: str) -> None:
        self.update(message)
        self.add_class("-shown")

    def clear(self) -> None:
        self.update("")
        self.remove_class("-shown")


class PasswordField(Vertical):
    """Password input with a Show/Hide button and an inline error line."""

    DEFAULT_CSS = """
    PasswordField {
        height: auto;
    }
    PasswordField Horizontal {
        height: auto;
        align-horizontal: left;
    }
    PasswordField Input {
        width: 1fr;
    }
    PasswordField Button {
        width: 10;
        margin-left: 1;
    }
    """

    def __init__(self, input_id: str, placeholder: str = "Password", **kwargs) -> None:
        super().__init__(**kwargs)
        self._input_id = input_id
        self._placeholder = placeholder

    @property
    def input(self) -> Input:
        return self.query_one(f"#{self._input_id}", Input)

    @property
    def value(self) -> str:
        return self.input.value

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Input(
                placeholder=self._placeholder,
                password=True,
                id=self._input_id,
                validators=password_validators(),
                valid_empty=True,
                validate_on=["blur", "submitted"],
            )
            yield Button("Show", id=f"{self._input_id}-toggle")
        yield FieldError("", id=f"{self._input_id}-error")

    def set_disabled(self, disabled: bool) -> None:
        self.input.disabled = disabled
        self.query_one(f"#{self._input_id}-toggle", Button).disabled = disabled
        if disabled:
            self.error.clear()

    @property
    def error(self) -> FieldError:
        return self.query_one(f"#{self._input_id}-error", FieldError)

    @on(Button.Pressed)
    def _toggle_visibility(self, event: Button.Pressed) -> None:
        if event.button.id != f"{self._input_id}-toggle":
            return
        event.stop()
        field = self.input
        field.password = not field.password
        event.button.label = "Show" if field.password else "Hide"

    @on(Input.Changed)
    def _clear_error(self, event: Input.Changed) -> None:
        if event.input.id == self._input_id:
            self.error.clear()


async def run_guarded(screen, factory: Callable[[], Awaitable[Any]]) -> tuple[bool, Any]:
    """Await ``factory()``; on failure notify on *screen* and return ``(False, None)``.

    Mirrors :meth:`fit_ctf_admin.widgets.core_widget.AdminPage._guarded`, but for
    dialogs that must survive the error instead of being dismissed.
    """
    try:
        return True, await factory()
    except AdminError as exc:
        screen.notify(str(exc), severity="error", timeout=ERROR_NOTIFY_TIMEOUT)
    except CTFBaseException as exc:  # safety net: gateways should map these
        screen.notify(str(exc), severity="error", timeout=ERROR_NOTIFY_TIMEOUT)
    except Exception as exc:  # never let a dialog worker die silently
        screen.notify(f"Unexpected error: {exc}", severity="error", timeout=ERROR_NOTIFY_TIMEOUT)
    return False, None
