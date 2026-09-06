"""Cluster gateway tests over both implementations.

The live gateway runs with ``CONTAINER_CLIENT=mock``: lifecycle calls succeed
(exit code 0) and ``compose_ps`` reports nothing, so live clusters always show
``running=False``. The preview gateway keeps explicit running flags.
"""

import pytest

from fit_ctf_admin.core.live_gateway import LiveGateway
from fit_ctf_admin.core.preview_gateway import PreviewGateway
from fit_ctf_admin.core.preview_store import PreviewStore
from fit_ctf_admin.core.protocols import AdminGateway
from fit_ctf_admin.exceptions import AdminError

STRONG_PASSWORD = "StrongPass123"


@pytest.fixture(params=["preview", "live"])
def gateway(request) -> AdminGateway:
    if request.param == "preview":
        return PreviewGateway(PreviewStore())
    ctf_app, _ = request.getfixturevalue("empty_data")
    return LiveGateway(ctf_app)


async def _setup(gateway: AdminGateway) -> None:
    await gateway.create_user("user_a", STRONG_PASSWORD, generate_password=False)
    await gateway.create_project("prj_a", 5)
    await gateway.enroll_user("user_a", "prj_a")


async def test_project_cluster_listed_after_project_creation(gateway: AdminGateway):
    await _setup(gateway)
    rows = await gateway.list_project_clusters()
    assert len(rows) == 1
    row = rows[0]
    assert row.kind == "project" and row.project == "prj_a"
    assert row.exists


async def test_user_cluster_listed_after_enrollment(gateway: AdminGateway):
    await _setup(gateway)
    rows = await gateway.list_user_clusters("prj_a")
    assert len(rows) == 1
    row = rows[0]
    assert (row.kind, row.username, row.project) == ("user", "user_a", "prj_a")
    assert row.exists


async def test_project_cluster_lifecycle_does_not_raise(gateway: AdminGateway):
    await _setup(gateway)
    await gateway.start_project_cluster("prj_a")
    await gateway.restart_project_cluster("prj_a")
    await gateway.stop_project_cluster("prj_a")


async def test_user_cluster_lifecycle_does_not_raise(gateway: AdminGateway):
    await _setup(gateway)
    await gateway.start_user_cluster("user_a", "prj_a")
    await gateway.restart_user_cluster("user_a", "prj_a")
    await gateway.stop_user_cluster("user_a", "prj_a")
    await gateway.stop_all_user_clusters("prj_a")


async def test_health_returns_rows_or_empty(gateway: AdminGateway):
    await _setup(gateway)
    health = await gateway.project_cluster_health("prj_a")
    assert isinstance(health, list)
    health = await gateway.user_cluster_health("user_a", "prj_a")
    assert isinstance(health, list)


async def test_lifecycle_on_unknown_project_raises(gateway: AdminGateway):
    with pytest.raises(AdminError):
        await gateway.start_project_cluster("ghost_project")


class TestPreviewFlags:
    async def test_start_stop_toggles_running(self):
        gateway = PreviewGateway(PreviewStore.with_sample_data())
        rows = {row.project: row for row in await gateway.list_project_clusters()}
        assert rows["intro_linux"].running
        assert not rows["web_exploitation"].running

        await gateway.start_project_cluster("web_exploitation")
        rows = {row.project: row for row in await gateway.list_project_clusters()}
        assert rows["web_exploitation"].running

    async def test_user_cluster_start_pulls_project_up(self):
        gateway = PreviewGateway(PreviewStore.with_sample_data())
        await gateway.start_user_cluster("dave", "web_exploitation")
        projects = {row.project: row for row in await gateway.list_project_clusters()}
        assert projects["web_exploitation"].running
        users = {row.username: row for row in await gateway.list_user_clusters("web_exploitation")}
        assert users["dave"].running

    async def test_stop_all_user_clusters(self):
        gateway = PreviewGateway(PreviewStore.with_sample_data())
        await gateway.stop_all_user_clusters("intro_linux")
        users = await gateway.list_user_clusters("intro_linux")
        assert all(not row.running for row in users)

    async def test_health_state_follows_running_flag(self):
        gateway = PreviewGateway(PreviewStore.with_sample_data())
        health = await gateway.project_cluster_health("intro_linux")
        assert health and all(row.state == "running" for row in health)
        await gateway.stop_project_cluster("intro_linux")
        health = await gateway.project_cluster_health("intro_linux")
        assert health and all(row.state == "exited" for row in health)
