"""Shared UI constants for the admin TUI."""

from __future__ import annotations

# (page_id, sidebar title) in sidebar order. Every page widget carries the
# page_id as its widget id; the sidebar derives its button ids from it.
PAGES: list[tuple[str, str]] = [
    ("dashboard-page", "Dashboard"),
    ("users-page", "Users"),
    ("projects-page", "Projects"),
    ("enrollments-page", "Enrollments"),
    ("clusters-page", "Clusters"),
    ("scenarios-page", "Scenarios"),
    ("designer-page", "Designer"),
    ("modules-page", "Modules"),
    ("progress-page", "Progress"),
    ("logs-page", "Logs"),
    ("sessions-page", "Sessions"),
]

INITIAL_PAGE = "dashboard-page"

ERROR_NOTIFY_TIMEOUT = 8
INFO_NOTIFY_TIMEOUT = 4
