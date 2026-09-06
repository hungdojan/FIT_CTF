"""Textual application object for the admin TUI."""

from __future__ import annotations

from textual.app import App

from fit_ctf_admin.core.admin_core import AdminCore
from fit_ctf_admin.screens.admin_screen.admin_screen import AdminScreen


class AdminApp(App):
    """Thin app shell; all state lives in the injected :class:`AdminCore`."""

    TITLE = "FIT-CTF Admin"

    def __init__(self, core: AdminCore, **kwargs) -> None:
        self.admin_core = core
        super().__init__(**kwargs)

    def on_mount(self) -> None:
        self.sub_title = self.admin_core.mode_label
        self.push_screen(AdminScreen())
