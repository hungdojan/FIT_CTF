"""Tiny input checks shared by both gateway implementations."""

from __future__ import annotations

from fit_ctf_admin.exceptions import AdminError


def required(value: str, label: str) -> str:
    """Strip *value* and raise :class:`AdminError` when it is empty."""
    value = value.strip()
    if not value:
        raise AdminError(f"{label} is required.")
    return value
