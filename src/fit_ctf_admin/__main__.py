"""Entry point: ``fit-admin-page [--preview]``.

All bootstrapping side effects (dotenv, env validation, Mongo connection,
share-dir creation via ``CTFApp``) happen here and only here.
"""

from __future__ import annotations

import argparse
import sys

import pymongo.errors
from dotenv import load_dotenv

from fit_ctf_admin.admin_app import AdminApp
from fit_ctf_admin.core.admin_core import AdminCore


def _connected_core() -> AdminCore:
    from fit_ctf.components.constants import get_env_info, get_paths
    from fit_ctf.components.types import PathDict
    from fit_ctf.ctf_app import CTFApp
    from fit_ctf.utils import CTFUtils

    env_info = get_env_info()
    paths = PathDict(
        **dict(zip(["projects", "users", "modules", "scenarios"], get_paths())),
    )
    mongo_client = CTFUtils.create_mongo_client(env_info)
    return AdminCore.connected(CTFApp(env_info, paths, mongo_client))


def main() -> None:
    parser = argparse.ArgumentParser(prog="fit-admin-page", description="FIT-CTF admin TUI")
    parser.add_argument(
        "--preview",
        action="store_true",
        help="run with in-memory sample data instead of connecting to MongoDB",
    )
    args = parser.parse_args()

    load_dotenv()
    if args.preview:
        core = AdminCore.preview()
    else:
        try:
            core = _connected_core()
        except pymongo.errors.ServerSelectionTimeoutError:
            sys.exit(
                "Could not connect to the database. "
                "Start MongoDB with `inv db-start`, or explore the UI with `--preview`."
            )

    AdminApp(core).run()


if __name__ == "__main__":
    main()
