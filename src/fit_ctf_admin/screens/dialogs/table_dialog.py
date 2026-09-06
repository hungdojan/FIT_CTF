"""Generic modal presenting tabular results (health checks, port listings…)."""

from __future__ import annotations

from typing import Iterable, Sequence

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Label


class TableDialog(ModalScreen[None]):
    DEFAULT_CSS = """
    TableDialog {
        align: center middle;
    }
    TableDialog > Vertical {
        width: 80;
        max-height: 80%;
        height: auto;
        padding: 1 2;
        border: heavy $primary;
        background: $surface;
    }
    TableDialog .dialog-title {
        text-style: bold;
        margin-bottom: 1;
    }
    TableDialog DataTable {
        max-height: 20;
        height: auto;
        margin-bottom: 1;
    }
    TableDialog Horizontal {
        height: auto;
        align-horizontal: right;
    }
    """

    BINDINGS = [("escape", "dismiss(None)", "Close")]

    def __init__(
        self,
        title: str,
        columns: Sequence[str],
        rows: Iterable[tuple],
        empty_message: str = "No results.",
    ) -> None:
        super().__init__()
        self._title = title
        self._columns = columns
        self._rows = list(rows)
        self._empty_message = empty_message

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(self._title, classes="dialog-title")
            if self._rows:
                yield DataTable(cursor_type="row", zebra_stripes=True)
            else:
                yield Label(self._empty_message)
            with Horizontal():
                yield Button("Close", variant="primary", id="table-dialog-close-btn")

    def on_mount(self) -> None:
        if self._rows:
            table = self.query_one(DataTable)
            table.add_columns(*self._columns)
            table.add_rows(self._rows)

    @on(Button.Pressed, "#table-dialog-close-btn")
    def _close(self) -> None:
        self.dismiss(None)
