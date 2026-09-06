"""Show a generated credential exactly once, behind an explicit dismiss."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static


class SecretRevealDialog(ModalScreen[None]):
    """Displays a one-time secret (e.g. generated password) until dismissed."""

    DEFAULT_CSS = """
    SecretRevealDialog {
        align: center middle;
    }
    SecretRevealDialog > Vertical {
        width: 64;
        height: auto;
        padding: 1 2;
        border: heavy $warning;
        background: $surface;
    }
    SecretRevealDialog .dialog-title {
        text-style: bold;
        margin-bottom: 1;
    }
    SecretRevealDialog .secret-value {
        text-style: bold;
        background: $boost;
        padding: 0 1;
        margin-bottom: 1;
    }
    SecretRevealDialog Horizontal {
        height: auto;
        align-horizontal: right;
    }
    """

    def __init__(self, title: str, secret: str, note: str = "") -> None:
        super().__init__()
        self._title = title
        self._secret = secret
        self._note = note or "Copy it now — it is not shown again."

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(self._title, classes="dialog-title")
            yield Static(self._secret, classes="secret-value")
            yield Static(self._note)
            with Horizontal():
                yield Button("Done", variant="primary", id="secret-done-btn")

    @on(Button.Pressed, "#secret-done-btn")
    def _done(self) -> None:
        self.dismiss(None)
