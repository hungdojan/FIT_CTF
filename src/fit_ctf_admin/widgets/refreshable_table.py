"""DataTable wrapper that reloads from DTO rows while keeping the cursor.

Tables created with ``selectable=True`` grow a leading marker column so several
rows can be picked for one bulk action (``space`` toggles, ``ctrl+a`` selects
all, ``ctrl+d`` clears); the marker state survives a reload for keys that still
exist.
"""

from __future__ import annotations

from typing import Iterable, Sequence

from textual.binding import Binding
from textual.coordinate import Coordinate
from textual.message import Message
from textual.widgets import DataTable

MARKER_COLUMN = "✓"
# plain glyphs on purpose: cell text goes through Rich markup, so "[x]" would be
# parsed as a tag and render as nothing
MARK_ON = "✓"
MARK_OFF = "·"


class RefreshableTable(DataTable):
    """A ``DataTable`` fed from DTO lists with stable row keys.

    ``set_data`` clears and repopulates the table; if the previously selected
    row key still exists, the cursor returns to it.
    """

    BINDINGS = [
        Binding("space", "toggle_row", "Toggle row", show=False),
        Binding("ctrl+a", "select_all", "Select all", show=False),
        Binding("ctrl+d", "clear_selection", "Clear selection", show=False),
    ]

    class SelectionChanged(Message):
        """Posted when the set of marked rows changed (also after a reload)."""

        def __init__(self, table: "RefreshableTable") -> None:
            self.table = table
            self.keys = table.selected_keys
            super().__init__()

        @property
        def control(self) -> "RefreshableTable":
            return self.table

    def __init__(self, *, selectable: bool = False, **kwargs) -> None:
        super().__init__(cursor_type="row", zebra_stripes=True, **kwargs)
        self._columns_set = False
        self._selectable = selectable
        self._keys: list[str] = []
        self._marked: set[str] = set()

    # -- data ------------------------------------------------------------------

    def set_data(
        self,
        columns: Sequence[str],
        rows: Iterable[tuple],
        keys: Sequence[str],
    ) -> None:
        selected = self.selected_key
        if not self._columns_set:
            header = (MARKER_COLUMN, *columns) if self._selectable else tuple(columns)
            self.add_columns(*header)
            self._columns_set = True
        self.clear()
        self._keys = list(keys)
        dropped = self._marked - set(self._keys)
        self._marked -= dropped
        for key, row in zip(keys, rows):
            cells = (self._marker(key), *row) if self._selectable else row
            self.add_row(*cells, key=key)
        if selected is not None and selected in keys:
            try:
                self.move_cursor(row=self.get_row_index(selected))
            except Exception:
                pass  # cursor restoration is best-effort
        if self._selectable:
            self.post_message(self.SelectionChanged(self))

    @property
    def selected_key(self) -> str | None:
        """Row key under the cursor, or ``None`` when the table is empty."""
        if self.row_count == 0:
            return None
        try:
            row_key, _ = self.coordinate_to_cell_key(self.cursor_coordinate)
        except Exception:
            return None
        return row_key.value

    # -- multi-select ----------------------------------------------------------

    @property
    def selected_keys(self) -> list[str]:
        """Marked row keys in table order (empty when nothing is marked)."""
        return [key for key in self._keys if key in self._marked]

    @property
    def action_keys(self) -> list[str]:
        """Keys a bulk action should apply to: the marked rows, else the cursor row."""
        marked = self.selected_keys
        if marked:
            return marked
        current = self.selected_key
        return [current] if current is not None else []

    def _marker(self, key: str) -> str:
        return MARK_ON if key in self._marked else MARK_OFF

    def _repaint_marker(self, key: str) -> None:
        try:
            row_index = self.get_row_index(key)
        except Exception:
            return
        self.update_cell_at(Coordinate(row_index, 0), self._marker(key))

    def toggle_key(self, key: str) -> None:
        if not self._selectable or key not in self._keys:
            return
        if key in self._marked:
            self._marked.discard(key)
        else:
            self._marked.add(key)
        self._repaint_marker(key)
        self.post_message(self.SelectionChanged(self))

    def clear_marks(self) -> None:
        if not self._marked:
            return
        keys = list(self._marked)
        self._marked.clear()
        for key in keys:
            self._repaint_marker(key)
        self.post_message(self.SelectionChanged(self))

    def action_toggle_row(self) -> None:
        key = self.selected_key
        if key is not None:
            self.toggle_key(key)

    def action_select_all(self) -> None:
        if not self._selectable or not self._keys:
            return
        self._marked = set(self._keys)
        for key in self._keys:
            self._repaint_marker(key)
        self.post_message(self.SelectionChanged(self))

    def action_clear_selection(self) -> None:
        self.clear_marks()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Clicking (or pressing enter on) a row toggles it in selectable tables."""
        if not self._selectable:
            return
        key = event.row_key.value
        if key is not None:
            self.toggle_key(key)
