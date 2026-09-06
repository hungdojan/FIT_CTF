"""Small modal asking for one text value."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label


class InputDialog(ModalScreen[str | None]):
    DEFAULT_CSS = """
    InputDialog {
        align: center middle;
    }
    InputDialog > Vertical {
        width: 60;
        height: auto;
        padding: 1 2;
        border: heavy $primary;
        background: $surface;
    }
    InputDialog .dialog-title {
        text-style: bold;
        margin-bottom: 1;
    }
    InputDialog Input {
        margin-bottom: 1;
    }
    InputDialog Horizontal {
        height: auto;
        align-horizontal: right;
    }
    InputDialog Horizontal Button {
        margin-left: 2;
    }
    """

    BINDINGS = [("escape", "dismiss(None)", "Cancel")]

    def __init__(
        self,
        title: str,
        placeholder: str = "",
        confirm_label: str = "OK",
        initial: str = "",
    ) -> None:
        super().__init__()
        self._title = title
        self._placeholder = placeholder
        self._confirm_label = confirm_label
        self._initial = initial

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(self._title, classes="dialog-title")
            yield Input(value=self._initial, placeholder=self._placeholder, id="input-dialog-value")
            with Horizontal():
                yield Button("Cancel", id="input-dialog-cancel-btn")
                yield Button(self._confirm_label, variant="primary", id="input-dialog-ok-btn")

    @on(Input.Submitted, "#input-dialog-value")
    @on(Button.Pressed, "#input-dialog-ok-btn")
    def _confirm(self) -> None:
        self.dismiss(self.query_one("#input-dialog-value", Input).value)

    @on(Button.Pressed, "#input-dialog-cancel-btn")
    def _cancel(self) -> None:
        self.dismiss(None)
