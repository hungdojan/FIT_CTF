import csv
from io import StringIO
import re

from fit_ctf_backend.cli import cli
from tests import CLIData, fixture_path


def test_cli_export_data(cli_data: CLIData):
    _, tmp_path, cli_runner = cli_data
    zip_path = tmp_path / "out.zip"
    cmd = f"data-mgmt export -pn prj3 -o {str(zip_path.resolve())}".split()
    result = cli_runner.invoke(cli, cmd)
    assert re.search("not exist.$", result.output)

    cmd = f"data-mgmt export -pn prj1 -o {str(zip_path.resolve())}".split()
    assert not zip_path.exists()
    result = cli_runner.invoke(cli, cmd)
    assert zip_path.exists()


def test_cli_import_data(empty_cli_data: CLIData):
    ctf_mgr, tmp_path, cli_runner = empty_cli_data
    zip_path = tmp_path / "out.zip"
    assert not ctf_mgr.prj_mgr.get_docs()
    assert not ctf_mgr.user_mgr.get_docs()
    assert not ctf_mgr.user_enrollment_mgr.get_docs()

    cmd = f"data-mgmt import -i {str(zip_path.resolve())}".split()
    result = cli_runner.invoke(cli, cmd)

    assert result.exit_code == 0

    assert ctf_mgr.prj_mgr.get_project("prj1")
    assert len(ctf_mgr.user_mgr.get_docs()) == 2
    assert len(ctf_mgr.user_enrollment_mgr.get_docs()) > 0

    # clean up
    zip_path.unlink()


def test_cli_setup(empty_cli_data: CLIData):
    ctf_mgr, _, cli_runner = empty_cli_data

    file = fixture_path() / "connected_data.yaml"
    assert not ctf_mgr.prj_mgr.get_docs()
    assert not ctf_mgr.user_mgr.get_docs()
    assert not ctf_mgr.user_enrollment_mgr.get_docs()

    cmd = f"data-mgmt setup -i {str(file.resolve())} -f csv"
    result = cli_runner.invoke(cli, cmd)

    f = StringIO(result.output)
    rows = [i for i in csv.reader(f)]
    assert len(rows[1:]) == len(ctf_mgr.user_mgr.get_docs())
    assert len(ctf_mgr.prj_mgr.get_docs()) == 2
