"""View and edit the files of a container module (Containerfile, entrypoint…)."""

from __future__ import annotations

from functools import partial

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Label, Select, TextArea

from fit_ctf_admin.constants import ERROR_NOTIFY_TIMEOUT
from fit_ctf_admin.exceptions import AdminError
from fit_ctf_admin.screens.dialogs.confirm_dialog import ConfirmDialog
from fit_ctf_admin.screens.editor_screen import EditorScreen


class ModuleFilesScreen(EditorScreen):
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

    def __init__(self, module_name: str) -> None:
        super().__init__()
        self._module_name = module_name
        self._current_file: str | None = None
        self._loaded_text: str | None = None
        self._reverting_select = False

    # -- unsaved-changes guard -------------------------------------------------

    def is_dirty(self) -> bool:
        if self._loaded_text is None:
            return False
        return self.query_one("#module-file-area", TextArea).text != self._loaded_text

    def discard_result(self) -> None:
        return None

    def discard_subject(self) -> str:
        return f"`{self._current_file}`" if self._current_file else "this file"

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
        if self._reverting_select:
            self._reverting_select = False
            return
        if event.value is Select.BLANK:
            return
        target = str(event.value)
        if target == self._current_file:
            return
        if self.is_dirty():
            self.app.push_screen(
                ConfirmDialog(
                    f"Discard unsaved changes to {self.discard_subject()}?",
                    f"Switching to `{target}` drops the edits.",
                    confirm_label="Discard",
                ),
                partial(self._switch_confirmed, target, self._current_file),
            )
            return
        self._start_load(target)

    def _switch_confirmed(self, target: str, previous: str | None, confirmed: bool | None) -> None:
        if confirmed:
            self._start_load(target)
            return
        if previous is not None:  # put the picker back on the edited file
            self._reverting_select = True
            self.query_one("#module-file-select", Select).value = previous

    def _start_load(self, file_name: str) -> None:
        self.run_worker(partial(self._load_file, file_name), exclusive=True, exit_on_error=False)

    async def _load_file(self, file_name: str) -> None:
        try:
            text = await self.core.gateway.read_module_file(self._module_name, file_name)
        except AdminError as exc:
            self.notify(str(exc), severity="error", timeout=ERROR_NOTIFY_TIMEOUT)
            return
        self._current_file = file_name
        self._loaded_text = text
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
        self._loaded_text = text
        self.notify(f"Saved `{file_name}` of module `{self._module_name}`.")

    @on(Button.Pressed, "#module-file-close-btn")
    def _close(self) -> None:
        self.request_close()
