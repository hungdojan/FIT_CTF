"""DataTable wrapper that reloads from DTO rows while keeping the cursor."""

from __future__ import annotations

from typing import Iterable, Sequence

from textual.widgets import DataTable


class RefreshableTable(DataTable):
    """A ``DataTable`` fed from DTO lists with stable row keys.

    ``set_data`` clears and repopulates the table; if the previously selected
    row key still exists, the cursor returns to it.
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(cursor_type="row", zebra_stripes=True, **kwargs)
        self._columns_set = False

    def set_data(
        self,
        columns: Sequence[str],
        rows: Iterable[tuple],
        keys: Sequence[str],
    ) -> None:
        selected = self.selected_key
        if not self._columns_set:
            self.add_columns(*columns)
            self._columns_set = True
        self.clear()
        for key, row in zip(keys, rows):
            self.add_row(*row, key=key)
        if selected is not None and selected in keys:
            try:
                self.move_cursor(row=self.get_row_index(selected))
            except Exception:
                pass  # cursor restoration is best-effort

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
