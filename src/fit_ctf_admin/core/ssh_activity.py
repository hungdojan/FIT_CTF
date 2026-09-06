"""Best-effort SSH activity extraction from login-node container logs.

There is no database record of SSH logins — the only trace is sshd output in
the user's login-node container. These helpers grep the compose logs for the
usual sshd patterns; rows exist only while the cluster is running and keep the
raw log line as detail (timestamp formats vary between images).
"""

from __future__ import annotations

import re

from fit_ctf_admin.dto import SessionRow

_SSH_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"Accepted (?:password|publickey) for (\S+)"), "LOGIN"),
    (re.compile(r"session opened for user (\S+)"), "LOGIN"),
    (re.compile(r"session closed for user (\S+)"), "LOGOUT"),
    (re.compile(r"Connection closed by (?:authenticating user )?(\S+)"), "DISCONNECT"),
    (re.compile(r"Invalid user (\S+)"), "FAILED"),
    (re.compile(r"Failed password for (?:invalid user )?(\S+)"), "FAILED"),
]


def parse_ssh_activity(username: str, log_text: str) -> list[SessionRow]:
    rows: list[SessionRow] = []
    for line in log_text.splitlines():
        for pattern, state in _SSH_PATTERNS:
            match = pattern.search(line)
            if match:
                rows.append(
                    SessionRow(
                        username=username,
                        kind="ssh",
                        state=state,
                        timestamp="",
                        detail=line.strip(),
                    )
                )
                break
    return rows
