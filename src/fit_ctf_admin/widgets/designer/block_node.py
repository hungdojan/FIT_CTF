"""Draggable service block rendered on the design canvas."""

from __future__ import annotations

from rich.text import Text
from textual import events
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget

from fit_ctf_admin.scenario.design_model import (
    BLOCK_HEIGHT,
    BLOCK_HEIGHT_EXPANDED,
    BLOCK_WIDTH,
    BLOCK_WIDTH_EXPANDED,
    ServiceBlock,
    format_env_compact,
    format_ports_compact,
    snap_coordinate,
)

_DRAG_CLICK_THRESHOLD = 2


class BlockNode(Widget):
    """Service block: click to select, click again to expand details."""

    DEFAULT_CSS = """
    BlockNode {
        position: absolute;
        width: 16;
        height: 3;
        layer: blocks;
        border: round $panel;
        background: $boost;
        padding: 0 1;
        content-align: left top;
    }

    BlockNode.selected {
        border: heavy $accent;
        background: $surface;
    }

    BlockNode.expanded {
        width: 30;
        height: 10;
        border: double $accent;
        background: $panel;
    }
    """

    selected: reactive[bool] = reactive(False)
    expanded: reactive[bool] = reactive(False)

    class Selected(Message):
        def __init__(self, block_id: str) -> None:
            self.block_id = block_id
            super().__init__()

    class ToggleExpand(Message):
        def __init__(self, block_id: str) -> None:
            self.block_id = block_id
            super().__init__()

    class Moved(Message):
        def __init__(self, block_id: str, x: int, y: int) -> None:
            self.block_id = block_id
            self.x = x
            self.y = y
            super().__init__()

    class RequestPan(Message):
        def __init__(self, event: events.MouseEvent) -> None:
            self.event = event
            super().__init__()

    def __init__(
        self,
        block: ServiceBlock,
        canvas_size_getter,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.block = block
        self._canvas_size_getter = canvas_size_getter
        self._dragging = False
        self._did_drag = False
        self._selected_at_press = False
        self._drag_start_screen: tuple[int, int] | None = None
        self._block_start: tuple[int, int] = (block.x, block.y)

    def on_mount(self) -> None:
        self._apply_geometry()

    def watch_selected(self, selected: bool) -> None:
        self.set_class(selected, "selected")

    def watch_expanded(self, expanded: bool) -> None:
        self.set_class(expanded, "expanded")
        self._apply_geometry(snap=True)
        self.refresh()

    def _block_size(self) -> tuple[int, int]:
        if self.expanded:
            return BLOCK_WIDTH_EXPANDED, BLOCK_HEIGHT_EXPANDED
        return BLOCK_WIDTH, BLOCK_HEIGHT

    def _canvas_size(self) -> tuple[int, int]:
        width, height = self._canvas_size_getter()
        block_w, block_h = self._block_size()
        return max(block_w, width), max(block_h, height)

    def _networks_text(self) -> str:
        return ", ".join(self.block.networks) or "—"

    def render(self) -> Text:
        if not self.expanded:
            return Text.assemble(
                (self.block.label, "bold"),
                "\n",
                (self.block.image_label, "dim"),
            )
        return Text.assemble(
            (self.block.label, "bold"),
            "\n",
            (f"key: {self.block.service_key}", "dim"),
            "\n",
            (f"image: {self.block.image_label}", "dim"),
            "\n",
            (f"net: {self._networks_text()}", "green"),
            "\n",
            (f"ports: {format_ports_compact(self.block.ports)}", "cyan"),
            "\n",
            (f"env: {format_env_compact(self.block.env_keys)}", "yellow"),
        )

    def _apply_geometry(self, *, snap: bool = False) -> None:
        if snap:
            self.block.x = snap_coordinate(self.block.x)
            self.block.y = snap_coordinate(self.block.y)
        block_w, block_h = self._block_size()
        canvas_w, canvas_h = self._canvas_size()
        max_x = max(0, canvas_w - block_w)
        max_y = max(0, canvas_h - block_h)
        self.block.x = max(0, min(snap_coordinate(self.block.x) if snap else self.block.x, max_x))
        self.block.y = max(0, min(snap_coordinate(self.block.y) if snap else self.block.y, max_y))
        self.styles.position = "absolute"
        self.styles.offset = (self.block.x, self.block.y)
        self.styles.width = block_w
        self.styles.height = block_h

    def on_mouse_down(self, event: events.MouseDown) -> None:
        if event.shift:
            self.post_message(self.RequestPan(event))
            return
        event.stop()
        self._selected_at_press = self.selected
        self._did_drag = False
        self.post_message(self.Selected(self.block.id))
        self.capture_mouse()
        self._dragging = True
        self._drag_start_screen = (event.screen_x, event.screen_y)
        self._block_start = (self.block.x, self.block.y)

    def on_mouse_move(self, event: events.MouseMove) -> None:
        if not self._dragging or self._drag_start_screen is None:
            return
        start_x, start_y = self._drag_start_screen
        origin_x, origin_y = self._block_start
        dx = event.screen_x - start_x
        dy = event.screen_y - start_y
        if abs(dx) + abs(dy) >= _DRAG_CLICK_THRESHOLD:
            self._did_drag = True
        self.block.x = origin_x + dx
        self.block.y = origin_y + dy
        self._apply_geometry(snap=False)

    def on_mouse_up(self, event: events.MouseUp) -> None:
        if not self._dragging:
            return
        event.stop()
        self._dragging = False
        self._drag_start_screen = None
        self.release_mouse()
        self._apply_geometry(snap=True)
        if self._did_drag:
            self.post_message(self.Moved(self.block.id, self.block.x, self.block.y))
        elif self._selected_at_press:
            self.post_message(self.ToggleExpand(self.block.id))

    def on_click(self, event: events.Click) -> None:
        event.stop()

    def nudge(self, dx: int, dy: int) -> None:
        self.block.x += dx
        self.block.y += dy
        self._apply_geometry(snap=True)
        self.post_message(self.Moved(self.block.id, self.block.x, self.block.y))

    def refresh_content(self) -> None:
        self.refresh()
