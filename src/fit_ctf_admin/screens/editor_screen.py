"""Base for full-screen editors that must not lose edits on escape.

Subclasses report whether they hold unsaved edits (:meth:`is_dirty`) and what to
dismiss with when the operator leaves (:meth:`discard_result`); escape and the
Cancel button then route through a confirmation instead of dropping the work.
"""

from __future__ import annotations

from typing import Any

from fit_ctf_admin.screens.base_screen import BaseScreen
from fit_ctf_admin.screens.dialogs.confirm_dialog import ConfirmDialog


class EditorScreen(BaseScreen):
    BINDINGS = [("escape", "close_editor", "Close")]

    #: what the confirmation calls the pending edits
    DISCARD_SUBJECT = "your changes"

    def is_dirty(self) -> bool:
        """True when leaving now would lose edits. Overridden by subclasses."""
        return False

    def discard_result(self) -> Any:
        """Value to dismiss with when the operator leaves without saving."""
        return False

    def action_close_editor(self) -> None:
        self.request_close()

    def request_close(self) -> None:
        if not self.is_dirty():
            self.dismiss(self.discard_result())
            return
        self.app.push_screen(
            ConfirmDialog(
                f"Discard unsaved changes to {self.discard_subject()}?",
                "The edits are lost. Cancel and use Save to keep them.",
                confirm_label="Discard",
            ),
            self._after_confirm,
        )

    def discard_subject(self) -> str:
        return self.DISCARD_SUBJECT

    def _after_confirm(self, confirmed: bool | None) -> None:
        if confirmed:
            self.dismiss(self.discard_result())
