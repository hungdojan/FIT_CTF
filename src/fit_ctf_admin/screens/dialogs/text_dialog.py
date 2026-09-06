"""Read-only text modal (compiled previews, reports…)."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, TextArea


class TextDialog(ModalScreen[None]):
    DEFAULT_CSS = """
    TextDialog {
        align: center middle;
    }
    TextDialog > Vertical {
        width: 100;
        max-width: 95%;
        height: 80%;
        padding: 1 2;
        border: heavy $primary;
        background: $surface;
    }
    TextDialog .dialog-title {
        text-style: bold;
        margin-bottom: 1;
    }
    TextDialog TextArea {
        height: 1fr;
        margin-bottom: 1;
    }
    TextDialog Horizontal {
        height: auto;
        align-horizontal: right;
    }
    """

    BINDINGS = [("escape", "dismiss(None)", "Close")]

    def __init__(self, title: str, text: str, *, language: str | None = "yaml") -> None:
        super().__init__()
        self._title = title
        self._text = text
        self._language = language

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(self._title, classes="dialog-title")
            yield TextArea(
                self._text,
                read_only=True,
                language=self._language,
                show_line_numbers=True,
                soft_wrap=False,
                id="text-dialog-area",
            )
            with Horizontal():
                yield Button("Close", variant="primary", id="text-dialog-close-btn")

    @on(Button.Pressed, "#text-dialog-close-btn")
    def _close(self) -> None:
        self.dismiss(None)
