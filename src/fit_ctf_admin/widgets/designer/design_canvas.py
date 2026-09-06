"""Canvas with draggable service blocks on a pannable world."""

from __future__ import annotations

from textual import events
from textual.app import ComposeResult
from textual.containers import Container
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget

from fit_ctf_admin.scenario.design_model import (
    WORLD_HEIGHT,
    WORLD_WIDTH,
    ScenarioDesign,
    ServiceBlock,
    snap_coordinate,
)
from fit_ctf_admin.widgets.designer.block_node import BlockNode


class DesignCanvas(Widget):
    """Pannable workspace for arranging service blocks."""

    DEFAULT_CSS = """
    DesignCanvas {
        width: 1fr;
        height: 1fr;
        border: round $primary;
        background: $surface;
    }

    DesignCanvas #viewport {
        width: 1fr;
        height: 1fr;
        overflow: hidden;
    }

    DesignCanvas #world {
        width: 120;
        height: 80;
        background: $surface-darken-1;
    }

    DesignCanvas #block-layer {
        width: 100%;
        height: 100%;
    }
    """

    _EMPTY_CANVAS_IDS = frozenset({"viewport", "block-layer", "world", "design-canvas"})

    selected_block_id: reactive[str | None] = reactive(None)
    expanded_block_id: reactive[str | None] = reactive(None)

    class SelectionChanged(Message):
        def __init__(self, block_id: str | None) -> None:
            self.block_id = block_id
            super().__init__()

    class DesignChanged(Message):
        pass

    def __init__(self, design: ScenarioDesign, **kwargs) -> None:
        super().__init__(**kwargs)
        self.design = design
        self._pan_x = 0
        self._pan_y = 0
        self._panning = False
        self._pan_start_screen: tuple[int, int] | None = None
        self._pan_start_offset: tuple[int, int] = (0, 0)

    def compose(self) -> ComposeResult:
        with Container(id="viewport"):
            with Container(id="world"):
                yield Container(id="block-layer")

    def on_mount(self) -> None:
        self.can_focus = True
        self._schedule_rebuild()
        self._apply_pan()

    def _world_size(self) -> tuple[int, int]:
        return WORLD_WIDTH, WORLD_HEIGHT

    def _viewport_size(self) -> tuple[int, int]:
        viewport = self.query_one("#viewport", Container)
        return max(1, viewport.size.width), max(1, viewport.size.height)

    def _clamp_pan(self) -> None:
        vp_w, vp_h = self._viewport_size()
        self._pan_x = max(0, min(self._pan_x, max(0, WORLD_WIDTH - vp_w)))
        self._pan_y = max(0, min(self._pan_y, max(0, WORLD_HEIGHT - vp_h)))

    def _apply_pan(self) -> None:
        self._clamp_pan()
        world = self.query_one("#world", Container)
        world.styles.offset = (-self._pan_x, -self._pan_y)

    def _is_block_widget(self, widget: Widget | None) -> bool:
        while widget is not None:
            if isinstance(widget, BlockNode):
                return True
            widget = widget.parent
        return False

    def _is_empty_canvas_click(self, widget: Widget | None) -> bool:
        if widget is None or self._is_block_widget(widget):
            return False
        widget_id = getattr(widget, "id", None)
        return widget_id in self._EMPTY_CANVAS_IDS

    def pan_by(self, dx: int, dy: int) -> None:
        self._pan_x += dx
        self._pan_y += dy
        self._apply_pan()

    def refresh_blocks(self, design: ScenarioDesign | None = None) -> None:
        """Public rebuild for hosts that swap or mutate the design object."""
        if design is not None:
            self.design = design
        self._schedule_rebuild()

    def watch_selected_block_id(self, block_id: str | None) -> None:
        for node in self.query(BlockNode):
            node.selected = node.block.id == block_id
        if self.expanded_block_id is not None and self.expanded_block_id != block_id:
            self.expanded_block_id = None
        self.post_message(self.SelectionChanged(block_id))

    def watch_expanded_block_id(self, expanded_id: str | None) -> None:
        for node in self.query(BlockNode):
            node.expanded = node.block.id == expanded_id

    def _schedule_rebuild(self) -> None:
        """Serialize rebuilds in a worker so they never race one another."""
        self.run_worker(self._rebuild_blocks, group="canvas-rebuild", exclusive=True)

    async def _rebuild_blocks(self) -> None:
        layer = self.query_one("#block-layer", Container)
        # the removal MUST complete before mounting: the new nodes reuse the
        # same block-<id> widget ids, otherwise Textual raises DuplicateIds
        await layer.remove_children()
        await layer.mount_all(
            BlockNode(block, self._world_size, id=f"block-{block.id}")
            for block in self.design.blocks
        )

    def reload_design(self, design: ScenarioDesign) -> None:
        self.design = design
        self.selected_block_id = None
        self.expanded_block_id = None
        self._schedule_rebuild()
        self.post_message(self.DesignChanged())

    def mount_block(self, block: ServiceBlock) -> None:
        """Mount an existing design block on the canvas (does not append to design)."""
        layer = self.query_one("#block-layer", Container)
        layer.mount(BlockNode(block, self._world_size, id=f"block-{block.id}"))
        self.selected_block_id = block.id
        self.post_message(self.DesignChanged())

    def add_service(self, module_name: str = "template") -> ServiceBlock:
        """Create a new service in the design and mount it on the canvas."""
        block = self.design.add_block(module_name=module_name)
        self.mount_block(block)
        return block

    def remove_selected(self) -> bool:
        if self.selected_block_id is None:
            return False
        removed = self.design.remove_block(self.selected_block_id)
        if not removed:
            return False
        self.selected_block_id = None
        self.expanded_block_id = None
        self._schedule_rebuild()
        self.post_message(self.DesignChanged())
        return True

    def get_selected_block(self) -> ServiceBlock | None:
        if self.selected_block_id is None:
            return None
        return self.design.get_block(self.selected_block_id)

    def update_selected_block(self, **changes) -> None:
        block = self.get_selected_block()
        if block is None:
            return
        for key, value in changes.items():
            setattr(block, key, value)
        node = self.query_one(f"#block-{block.id}", BlockNode)
        node.refresh_content()
        node._apply_geometry(snap=True)
        self.post_message(self.DesignChanged())

    def nudge_selected(self, dx: int, dy: int) -> None:
        block = self.get_selected_block()
        if block is None:
            return
        self.query_one(f"#block-{block.id}", BlockNode).nudge(dx, dy)

    def _start_pan(self, event: events.MouseEvent) -> None:
        self._panning = True
        self.capture_mouse()
        self._pan_start_screen = (event.screen_x, event.screen_y)
        self._pan_start_offset = (self._pan_x, self._pan_y)

    def _update_pan(self, event: events.MouseEvent) -> None:
        if not self._panning or self._pan_start_screen is None:
            return
        start_x, start_y = self._pan_start_screen
        origin_x, origin_y = self._pan_start_offset
        self._pan_x = origin_x + (start_x - event.screen_x)
        self._pan_y = origin_y + (start_y - event.screen_y)
        self._apply_pan()

    def _end_pan(self) -> None:
        if not self._panning:
            return
        self._panning = False
        self._pan_start_screen = None
        self.release_mouse()

    def on_mouse_down(self, event: events.MouseDown) -> None:
        if event.button != 1 and event.button != 2:
            return
        if self._is_block_widget(event.widget):
            return
        pan_with_modifier = event.shift or event.button == 2
        pan_on_empty = event.button == 1 and self._is_empty_canvas_click(event.widget)
        if pan_with_modifier or pan_on_empty:
            event.stop()
            self._start_pan(event)

    def on_mouse_move(self, event: events.MouseMove) -> None:
        if self._panning:
            event.stop()
            self._update_pan(event)

    def on_mouse_up(self, event: events.MouseUp) -> None:
        if self._panning:
            event.stop()
            self._end_pan()

    def on_mouse_scroll(self, event: events.MouseScroll) -> None:
        event.stop()
        self.pan_by(0, snap_coordinate(int(event.delta_y)))

    def on_click(self, event: events.Click) -> None:
        if self._is_empty_canvas_click(event.widget):
            self.selected_block_id = None
            self.expanded_block_id = None

    def on_block_node_request_pan(self, message: BlockNode.RequestPan) -> None:
        message.stop()
        self._start_pan(message.event)

    def on_block_node_selected(self, message: BlockNode.Selected) -> None:
        message.stop()
        if message.block_id != self.selected_block_id:
            self.expanded_block_id = None
        self.selected_block_id = message.block_id

    def on_block_node_toggle_expand(self, message: BlockNode.ToggleExpand) -> None:
        message.stop()
        if message.block_id != self.selected_block_id:
            return
        self.expanded_block_id = (
            None if self.expanded_block_id == message.block_id else message.block_id
        )

    def on_block_node_moved(self, message: BlockNode.Moved) -> None:
        message.stop()
        block = self.design.get_block(message.block_id)
        if block is None:
            return
        block.x = message.x
        block.y = message.y
        self.post_message(self.DesignChanged())

    def on_resize(self, _event) -> None:
        self._apply_pan()
        for node in self.query(BlockNode):
            node._apply_geometry(snap=True)
