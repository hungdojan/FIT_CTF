"""Base class for content pages: core access + safe gateway workers."""

from __future__ import annotations

from functools import partial
from typing import Any, Awaitable, Callable

from textual.containers import Vertical

from fit_ctf.exceptions import CTFBaseException
from fit_ctf_admin.constants import ERROR_NOTIFY_TIMEOUT
from fit_ctf_admin.core.admin_core import AdminCore
from fit_ctf_admin.exceptions import AdminError


class AdminPage(Vertical):
    """A sidebar-selectable content page.

    Pages implement :meth:`refresh_page` (called every time the page becomes
    visible) and run all gateway calls through :meth:`call_gateway`, which
    routes errors into notifications instead of crashing the worker.
    """

    @property
    def core(self) -> AdminCore:
        return self.app.admin_core  # type: ignore[attr-defined]

    def refresh_page(self) -> None:
        """Reload the page's data. Overridden by concrete pages."""

    def on_show(self) -> None:
        self.refresh_page()

    def call_gateway(
        self,
        factory: Callable[[], Awaitable[Any]],
        on_success: Callable[[Any], None] | None = None,
        *,
        group: str = "gateway",
        exclusive: bool = True,
    ) -> None:
        """Run a gateway call in a worker; surface AdminError as a toast.

        *factory* is a zero-arg callable producing the awaitable (e.g.
        ``lambda: self.core.gateway.list_users()``). Passing a factory instead
        of a ready coroutine matters: exclusive workers that are replaced
        before they start would otherwise leave the coroutine un-awaited
        ("coroutine … was never awaited" RuntimeWarning).
        """
        self.run_worker(
            partial(self._guarded, factory, on_success),
            group=group,
            exclusive=exclusive,
            exit_on_error=False,
        )

    async def _guarded(
        self, factory: Callable[[], Awaitable[Any]], on_success: Callable[[Any], None] | None
    ) -> None:
        try:
            result = await factory()
        except AdminError as exc:
            self.notify(str(exc), severity="error", timeout=ERROR_NOTIFY_TIMEOUT)
            return
        except CTFBaseException as exc:  # safety net: gateways should map these
            self.notify(str(exc), severity="error", timeout=ERROR_NOTIFY_TIMEOUT)
            return
        except Exception as exc:  # never let a page worker die silently
            self.notify(f"Unexpected error: {exc}", severity="error", timeout=ERROR_NOTIFY_TIMEOUT)
            return
        if on_success is not None:
            on_success(result)
