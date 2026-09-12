"""Live build log for ``podman/docker build``.

The modal opens as soon as the build starts and appends output while it runs, so
a slow image build shows progress instead of a silent wait. The exit state is
reported in the banner *and* as a notification.
"""

from __future__ import annotations

from typing import Awaitable, Callable

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Log, Static

from fit_ctf.exceptions import CTFBaseException
from fit_ctf_admin.constants import ERROR_NOTIFY_TIMEOUT
from fit_ctf_admin.exceptions import AdminError

BuildCallback = Callable[[Callable[[str], None]], Awaitable[bool]]


class BuildLogScreen(ModalScreen[bool | None]):
    """Runs *build* and streams its output; dismisses with the success flag."""

    DEFAULT_CSS = """
    BuildLogScreen {
        align: center middle;
    }
    BuildLogScreen > Vertical {
        width: 100;
        max-width: 95%;
        height: 80%;
        padding: 1 2;
        border: heavy $primary;
        background: $surface;
    }
    BuildLogScreen .dialog-title {
        text-style: bold;
        margin-bottom: 1;
    }
    BuildLogScreen Log {
        height: 1fr;
        margin-bottom: 1;
    }
    BuildLogScreen #build-status {
        height: auto;
        margin-bottom: 1;
    }
    BuildLogScreen #build-status.-ok {
        color: $success;
    }
    BuildLogScreen #build-status.-failed {
        color: $error;
    }
    BuildLogScreen Horizontal {
        height: auto;
        align-horizontal: right;
    }
    """

    BINDINGS = [("escape", "close", "Close")]

    def __init__(self, title: str, build: BuildCallback) -> None:
        super().__init__()
        self._title = title
        self._build = build
        # NB: not `_running` -- that name belongs to Textual's MessagePump
        self._build_running = True
        self._build_success = False

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(self._title, classes="dialog-title")
            yield Log(id="build-log", auto_scroll=True)
            yield Static("Building…", id="build-status")
            with Horizontal():
                yield Button("Close", id="build-log-close-btn", disabled=True)

    def on_mount(self) -> None:
        self._run_build()

    def append(self, line: str) -> None:
        self.query_one("#build-log", Log).write_line(line)

    @work
    async def _run_build(self) -> None:
        try:
            success = await self._build(self.append)
        except AdminError as exc:
            self._finish(False, str(exc))
            return
        except CTFBaseException as exc:  # safety net: gateways should map these
            self._finish(False, str(exc))
            return
        except Exception as exc:  # never let the build worker die silently
            self._finish(False, f"Unexpected error: {exc}")
            return
        self._finish(success, None)

    def _finish(self, success: bool, error: str | None) -> None:
        self._build_running = False
        status = self.query_one("#build-status", Static)
        close_btn = self.query_one("#build-log-close-btn", Button)
        close_btn.disabled = False
        close_btn.variant = "primary"
        if error is not None:
            self.append(error)
        if success:
            status.update("Build finished successfully.")
            status.add_class("-ok")
            self.notify("Image built.")
        else:
            status.update(error or "Build failed — see the log above.")
            status.add_class("-failed")
            self.notify(error or "Build failed.", severity="error", timeout=ERROR_NOTIFY_TIMEOUT)
        close_btn.focus()
        self._build_success = success

    def action_close(self) -> None:
        if self._build_running:
            self.notify("The build is still running.", severity="warning")
            return
        self.dismiss(self._build_success)

    @on(Button.Pressed, "#build-log-close-btn")
    def _close(self) -> None:
        self.action_close()


__all__ = ["BuildLogScreen", "BuildCallback"]
