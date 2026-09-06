"""Shared password handling for user creation in both gateways."""

from __future__ import annotations

from fit_ctf.components.auth.auth_interface import AuthInterface
from fit_ctf.components.constants import DEFAULT_PASSWORD_LENGTH
from fit_ctf_admin.exceptions import AdminError


def resolve_new_password(password: str | None, generate: bool) -> str:
    """Return the plaintext password for a new user, or raise :class:`AdminError`."""
    if generate:
        return AuthInterface.generate_password(DEFAULT_PASSWORD_LENGTH)
    if not password:
        raise AdminError("Enter a password or enable password generation.")
    if not AuthInterface.validate_password_strength(password):
        raise AdminError(
            "Password is not strong enough. It needs at least "
            f"{DEFAULT_PASSWORD_LENGTH} characters with lower/upper case letters and digits."
        )
    return password
