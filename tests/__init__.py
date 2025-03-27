import os
import pathlib
from typing import TypeAlias

from click.testing import CliRunner

import fit_ctf_backend.ctf_manager as ctf_mgr

FixtureData: TypeAlias = tuple["ctf_mgr.CTFManager", pathlib.Path]
CLIData: TypeAlias = tuple["ctf_mgr.CTFManager", pathlib.Path, CliRunner]


def fixture_path() -> pathlib.Path:
    return pathlib.Path(os.path.dirname(os.path.realpath(__file__))) / "fixtures"


__all__ = ["FixtureData", "fixture_path"]
