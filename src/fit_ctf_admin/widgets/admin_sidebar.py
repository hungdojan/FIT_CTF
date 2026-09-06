"""Navigation sidebar listing the content pages."""

from __future__ import annotations

from typing import Callable

from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Button, Label, Rule

from fit_ctf_admin.constants import PAGES


class AdminSidebar(Vertical):
    """One button per page; the active page's button gets ``-active-page``."""

    def __init__(self, on_page_select: Callable[[str], None], mode_label: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self._on_page_select = on_page_select
        self._mode_label = mode_label

    def compose(self) -> ComposeResult:
        yield Label("FIT-CTF Admin", id="sidebar-title")
        yield Rule(line_style="ascii")
        with VerticalScroll(id="sidebar-nav"):
            for page_id, title in PAGES:
                yield Button(title, id=f"nav-{page_id}")
        yield Rule(line_style="ascii")
        yield Label(self._mode_label, id="sidebar-mode-label")

    @on(Button.Pressed)
    def _page_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id and event.button.id.startswith("nav-"):
            event.stop()
            self._on_page_select(event.button.id.removeprefix("nav-"))

    def mark_active(self, page_id: str) -> None:
        for button in self.query(Button):
            button.set_class(button.id == f"nav-{page_id}", "-active-page")
