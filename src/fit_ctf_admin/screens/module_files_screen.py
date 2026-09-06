"""View and edit the files of a container module (Containerfile, entrypoint…)."""

from __future__ import annotations

from functools import partial

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Label, Select, TextArea

from fit_ctf_admin.constants import ERROR_NOTIFY_TIMEOUT
from fit_ctf_admin.exceptions import AdminError
from fit_ctf_admin.screens.base_screen import BaseScreen


class ModuleFilesScreen(BaseScreen):
    DEFAULT_CSS = """
    ModuleFilesScreen Vertical {
        padding: 0 2;
    }
    ModuleFilesScreen .screen-title {
        text-style: bold;
        margin: 1 0;
    }
    ModuleFilesScreen .toolbar {
        height: auto;
        margin-bottom: 1;
    }
    ModuleFilesScreen .toolbar Button {
        margin-left: 2;
    }
    ModuleFilesScreen TextArea {
        height: 1fr;
        margin-bottom: 1;
    }
    """

    BINDINGS = [("escape", "dismiss(None)", "Close")]

    def __init__(self, module_name: str) -> None:
        super().__init__()
        self._module_name = module_name
        self._current_file: str | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            yield Label(f"Files of module `{self._module_name}`", classes="screen-title")
            with Horizontal(classes="toolbar"):
                yield Select([], prompt="File", id="module-file-select")
                yield Button("Save file", variant="primary", id="module-file-save-btn")
                yield Button("Close", id="module-file-close-btn")
            yield TextArea("", id="module-file-area", show_line_numbers=True)
        yield Footer()

    def on_mount(self) -> None:
        self.run_worker(self._load_files, exclusive=True, exit_on_error=False)

    async def _load_files(self) -> None:
        try:
            files = await self.core.gateway.list_module_files(self._module_name)
        except AdminError as exc:
            self.notify(str(exc), severity="error", timeout=ERROR_NOTIFY_TIMEOUT)
            return
        select = self.query_one("#module-file-select", Select)
        select.set_options((name, name) for name in files)
        if files:
            select.value = files[0]

    @on(Select.Changed, "#module-file-select")
    def _file_selected(self, event: Select.Changed) -> None:
        if event.value is Select.BLANK:
            return
        self.run_worker(
            partial(self._load_file, str(event.value)), exclusive=True, exit_on_error=False
        )

    async def _load_file(self, file_name: str) -> None:
        try:
            text = await self.core.gateway.read_module_file(self._module_name, file_name)
        except AdminError as exc:
            self.notify(str(exc), severity="error", timeout=ERROR_NOTIFY_TIMEOUT)
            return
        self._current_file = file_name
        self.query_one("#module-file-area", TextArea).text = text

    @on(Button.Pressed, "#module-file-save-btn")
    def _save(self) -> None:
        if self._current_file is None:
            self.notify("Pick a file first.", severity="warning")
            return
        text = self.query_one("#module-file-area", TextArea).text
        self.run_worker(
            partial(self._run_save, self._current_file, text),
            exclusive=True,
            exit_on_error=False,
        )

    async def _run_save(self, file_name: str, text: str) -> None:
        try:
            await self.core.gateway.save_module_file(self._module_name, file_name, text)
        except AdminError as exc:
            self.notify(str(exc), severity="error", timeout=ERROR_NOTIFY_TIMEOUT)
            return
        self.notify(f"Saved `{file_name}` of module `{self._module_name}`.")

    @on(Button.Pressed, "#module-file-close-btn")
    def _close(self) -> None:
        self.dismiss(None)
