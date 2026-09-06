"""Modal confirmation used by every destructive action."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static


class ConfirmDialog(ModalScreen[bool]):
    """Ask the operator to confirm; dismisses with ``True``/``False``."""

    DEFAULT_CSS = """
    ConfirmDialog {
        align: center middle;
    }
    ConfirmDialog > Vertical {
        width: 60;
        height: auto;
        padding: 1 2;
        border: heavy $error;
        background: $surface;
    }
    ConfirmDialog .dialog-title {
        text-style: bold;
        margin-bottom: 1;
    }
    ConfirmDialog .dialog-detail {
        margin-bottom: 1;
    }
    ConfirmDialog Horizontal {
        height: auto;
        align-horizontal: right;
    }
    ConfirmDialog Button {
        margin-left: 2;
    }
    """

    BINDINGS = [("escape", "dismiss(False)", "Cancel")]

    def __init__(self, title: str, detail: str = "", confirm_label: str = "Delete") -> None:
        super().__init__()
        self._title = title
        self._detail = detail
        self._confirm_label = confirm_label

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(self._title, classes="dialog-title")
            if self._detail:
                yield Static(self._detail, classes="dialog-detail")
            with Horizontal():
                yield Button("Cancel", id="confirm-cancel-btn")
                yield Button(self._confirm_label, variant="error", id="confirm-ok-btn")

    @on(Button.Pressed, "#confirm-ok-btn")
    def _confirm(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#confirm-cancel-btn")
    def _cancel(self) -> None:
        self.dismiss(False)
