"""Screen base class exposing the shared :class:`AdminCore`."""

from __future__ import annotations

from textual.screen import Screen

from fit_ctf_admin.core.admin_core import AdminCore


class BaseScreen(Screen):
    @property
    def core(self) -> AdminCore:
        return self.app.admin_core  # type: ignore[attr-defined]
