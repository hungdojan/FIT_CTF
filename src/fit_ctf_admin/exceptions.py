"""User-facing exceptions for the admin TUI.

Every error that leaves the gateway layer is an :class:`AdminError`. The
`fit_ctf` domain exceptions derive from ``BaseException`` (not ``Exception``),
so they must be mapped explicitly — a bare ``except Exception`` misses them.
"""


class AdminError(Exception):
    """A recoverable error meant to be shown to the operator."""


class AdminConnectionError(AdminError):
    """The MongoDB backend could not be reached."""
