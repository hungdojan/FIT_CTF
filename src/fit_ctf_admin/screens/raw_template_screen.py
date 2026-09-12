"""Raw ``scenario_compose.yaml.j2`` editor — escape hatch for foreign scenarios."""

from __future__ import annotations

from functools import partial

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Label, TextArea

from fit_ctf_admin.constants import ERROR_NOTIFY_TIMEOUT
from fit_ctf_admin.exceptions import AdminError
from fit_ctf_admin.screens.editor_screen import EditorScreen


class RawTemplateScreen(EditorScreen):
    """Dismisses ``True`` after saving."""

    DEFAULT_CSS = """
    RawTemplateScreen Vertical {
        padding: 0 2;
    }
    RawTemplateScreen .screen-title {
        text-style: bold;
        margin: 1 0;
    }
    RawTemplateScreen TextArea {
        height: 1fr;
        margin-bottom: 1;
    }
    RawTemplateScreen Horizontal {
        height: auto;
    }
    RawTemplateScreen Horizontal Button {
        margin-right: 2;
    }
    """

    def __init__(self, scenario_name: str, text: str) -> None:
        super().__init__()
        self._scenario_name = scenario_name
        self._text = text

    def is_dirty(self) -> bool:
        return self.query_one("#raw-template-area", TextArea).text != self._text

    def discard_subject(self) -> str:
        return f"the template of `{self._scenario_name}`"

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            yield Label(
                f"Raw template of `{self._scenario_name}` (scenario_compose.yaml.j2)",
                classes="screen-title",
            )
            yield TextArea(self._text, id="raw-template-area", show_line_numbers=True)
            with Horizontal():
                yield Button("Save", variant="primary", id="raw-save-btn")
                yield Button("Cancel", id="raw-cancel-btn")
        yield Footer()

    @on(Button.Pressed, "#raw-save-btn")
    def _save(self) -> None:
        text = self.query_one("#raw-template-area", TextArea).text
        self.run_worker(partial(self._run_save, text), exclusive=True, exit_on_error=False)

    async def _run_save(self, text: str) -> None:
        try:
            await self.core.gateway.save_raw_template(self._scenario_name, text)
        except AdminError as exc:
            self.notify(str(exc), severity="error", timeout=ERROR_NOTIFY_TIMEOUT)
            return
        self._text = text
        self.notify(f"Template of `{self._scenario_name}` saved.")
        self.dismiss(True)

    @on(Button.Pressed, "#raw-cancel-btn")
    def _cancel(self) -> None:
        self.request_close()
