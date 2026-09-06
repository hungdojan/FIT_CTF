"""Facade the TUI talks to: gateway access, mode info, cross-page selection."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from fit_ctf_admin.core.preview_gateway import PreviewGateway
from fit_ctf_admin.core.protocols import AdminGateway

if TYPE_CHECKING:
    from fit_ctf.ctf_app import CTFApp

PREVIEW_MODE_LABEL = "Preview mode — sample data in memory, nothing is persisted"
CONNECTED_MODE_LABEL = "Connected to MongoDB"


class AdminCore:
    """Holds the gateway and light cross-page state (selected project).

    The core never reads env vars or opens connections itself — bootstrapping
    lives in ``__main__``. That keeps the admin screens embeddable into other
    apps (e.g. rendezvous) later.
    """

    def __init__(self, gateway: AdminGateway, *, is_preview: bool, mode_label: str) -> None:
        self.gateway = gateway
        self.is_preview = is_preview
        self.mode_label = mode_label
        self._selected_project: str | None = None
        self._selection_hooks: dict[str, Callable[[str | None], None]] = {}

    @classmethod
    def connected(cls, ctf_app: "CTFApp") -> "AdminCore":
        from fit_ctf_admin.core.live_gateway import LiveGateway

        return cls(LiveGateway(ctf_app), is_preview=False, mode_label=CONNECTED_MODE_LABEL)

    @classmethod
    def preview(cls) -> "AdminCore":
        return cls(PreviewGateway(), is_preview=True, mode_label=PREVIEW_MODE_LABEL)

    # -- cross-page selection ----------------------------------------------

    @property
    def selected_project(self) -> str | None:
        return self._selected_project

    @selected_project.setter
    def selected_project(self, value: str | None) -> None:
        self._selected_project = value
        for callback in self._selection_hooks.values():
            callback(value)

    def register_selection_hook(self, name: str, callback: Callable[[str | None], None]) -> None:
        self._selection_hooks[name] = callback

    def unregister_selection_hook(self, name: str) -> None:
        self._selection_hooks.pop(name, None)
