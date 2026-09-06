"""Main shell: sidebar navigation + content switcher of pages."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import ContentSwitcher, Footer, Header

from fit_ctf_admin.constants import INITIAL_PAGE, PAGES
from fit_ctf_admin.screens.base_screen import BaseScreen
from fit_ctf_admin.widgets.admin_sidebar import AdminSidebar
from fit_ctf_admin.widgets.content_pages import build_page

PAGE_KEY_BINDINGS = [
    (str(index + 1), f"show_page('{page_id}')", title)
    for index, (page_id, title) in enumerate(PAGES[:9])
]


class AdminScreen(BaseScreen):
    CSS_PATH = "admin_screen_styles.tcss"
    BINDINGS = [*PAGE_KEY_BINDINGS, ("ctrl+r", "refresh_page", "Refresh")]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="admin-main-layout"):
            yield AdminSidebar(
                on_page_select=self.show_page,
                mode_label=self.core.mode_label,
                id="admin-sidebar",
            )
            with ContentSwitcher(initial=INITIAL_PAGE, id="admin-content"):
                for page_id, _ in PAGES:
                    yield build_page(page_id)
        yield Footer()

    def on_mount(self) -> None:
        self.query_one(AdminSidebar).mark_active(INITIAL_PAGE)

    @property
    def switcher(self) -> ContentSwitcher:
        return self.query_one("#admin-content", ContentSwitcher)

    def show_page(self, page_id: str) -> None:
        if page_id not in {pid for pid, _ in PAGES}:
            return
        self.switcher.current = page_id
        self.query_one(AdminSidebar).mark_active(page_id)

    def action_show_page(self, page_id: str) -> None:
        self.show_page(page_id)

    def action_refresh_page(self) -> None:
        current = self.switcher.current
        if current is None:
            return
        page = self.switcher.get_child_by_id(current)
        refresh = getattr(page, "refresh_page", None)
        if callable(refresh):
            refresh()
