from __future__ import annotations
import os
import sys


def _get_db_info() -> tuple[str, str]:
    db_host = os.getenv("DB_HOST")
    if not db_host:
        sys.exit("Environment variable `DB_HOST` is not set.")

    db_name = os.getenv("DB_NAME")
    if not db_name:
        sys.exit("Environment variable `DB_NAME` is not set.")
    return db_host, db_name
