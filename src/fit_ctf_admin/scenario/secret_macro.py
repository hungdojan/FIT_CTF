"""Runtime secret generation: the ``<gen>`` macro.

A secret *value* may contain ``<gen>`` (32 random alphanumeric characters) or
``<gen:N>`` (custom length, 1–256). The macro is expanded when the config is
**applied** — every occurrence gets fresh randomness and the resolved value is
what gets persisted on the cluster (MongoDB). It composes inline:
``FLAG{<gen>}`` stores a wrapped flag, bare ``<gen>`` a raw token.

Validation deliberately leaves macros untouched so no randomness is consumed
before the operator saves.
"""

from __future__ import annotations

import re

from fit_ctf.components.auth.auth_interface import AuthInterface
from fit_ctf_admin.exceptions import AdminError

DEFAULT_GENERATED_LENGTH = 32
MAX_GENERATED_LENGTH = 256

_GEN_MACRO_RE = re.compile(r"<gen(?::(\d+))?>")


def random_token(length: int = DEFAULT_GENERATED_LENGTH) -> str:
    """Random alphanumeric token (safe inside YAML and Jinja templates)."""
    return AuthInterface.generate_password(length)


def _expand_value(key: str, value: str) -> str:
    def _replace(match: re.Match[str]) -> str:
        length = int(match.group(1)) if match.group(1) else DEFAULT_GENERATED_LENGTH
        if not 1 <= length <= MAX_GENERATED_LENGTH:
            raise AdminError(
                f"Secret '{key}': <gen:{length}> is out of range (1–{MAX_GENERATED_LENGTH})."
            )
        return random_token(length)

    return _GEN_MACRO_RE.sub(_replace, value)


def expand_secret_macros(secrets: dict[str, str]) -> dict[str, str]:
    """Return a copy of *secrets* with every ``<gen>``/``<gen:N>`` expanded."""
    return {key: _expand_value(key, value) for key, value in secrets.items()}
