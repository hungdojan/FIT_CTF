"""Modal form for one volume slot of a service."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, Select, TextArea

from fit_ctf_admin.scenario.design_model import VolumeSlot

KIND_OPTIONS = [
    ("Host path (set at assignment)", "path"),
    ("Static file (content below)", "static"),
    ("Template file (Jinja, may use secret_map__*)", "template"),
]


class VolumeSlotDialog(ModalScreen[VolumeSlot | None]):
    DEFAULT_CSS = """
    VolumeSlotDialog {
        align: center middle;
    }
    VolumeSlotDialog > Vertical {
        width: 80;
        height: auto;
        max-height: 90%;
        padding: 1 2;
        border: heavy $primary;
        background: $surface;
    }
    VolumeSlotDialog .dialog-title {
        text-style: bold;
        margin-bottom: 1;
    }
    VolumeSlotDialog Input, VolumeSlotDialog Select, VolumeSlotDialog Checkbox {
        margin-bottom: 1;
    }
    VolumeSlotDialog TextArea {
        height: 8;
        margin-bottom: 1;
    }
    VolumeSlotDialog Horizontal {
        height: auto;
        align-horizontal: right;
    }
    VolumeSlotDialog Horizontal Button {
        margin-left: 2;
    }
    """

    BINDINGS = [("escape", "dismiss(None)", "Cancel")]

    def __init__(self, slot: VolumeSlot | None = None) -> None:
        super().__init__()
        self._slot = slot

    def compose(self) -> ComposeResult:
        slot = self._slot
        with Vertical():
            yield Label("Volume slot", classes="dialog-title")
            yield Input(
                value=slot.name if slot else "",
                placeholder="volume name (slug, e.g. cfg)",
                id="volume-name",
            )
            yield Input(
                value=slot.container_path if slot else "",
                placeholder="container path (e.g. /data)",
                id="volume-container-path",
            )
            yield Checkbox("Read only", value=slot.read_only if slot else True, id="volume-ro")
            yield Select(
                KIND_OPTIONS,
                value=slot.kind if slot else "path",
                allow_blank=False,
                id="volume-kind",
            )
            yield TextArea(slot.body if slot else "", id="volume-body")
            with Horizontal():
                yield Button("Cancel", id="volume-cancel-btn")
                yield Button("Save", variant="primary", id="volume-save-btn")

    @on(Button.Pressed, "#volume-save-btn")
    def _save(self) -> None:
        try:
            slot = VolumeSlot(
                name=self.query_one("#volume-name", Input).value,
                container_path=self.query_one("#volume-container-path", Input).value,
                read_only=self.query_one("#volume-ro", Checkbox).value,
                kind=str(self.query_one("#volume-kind", Select).value),  # type: ignore[arg-type]
                body=self.query_one("#volume-body", TextArea).text,
            )
        except ValueError as exc:
            self.notify(str(exc), severity="error")
            return
        self.dismiss(slot)

    @on(Button.Pressed, "#volume-cancel-btn")
    def _cancel(self) -> None:
        self.dismiss(None)
