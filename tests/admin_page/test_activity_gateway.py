"""Progress / logs / sessions gateway tests."""

import pytest

from fit_ctf_admin.core.live_gateway import LiveGateway
from fit_ctf_admin.core.preview_gateway import PreviewGateway
from fit_ctf_admin.core.preview_store import PreviewStore
from fit_ctf_admin.core.ssh_activity import parse_ssh_activity
from fit_ctf_admin.exceptions import AdminError
from tests import FixtureData


class TestLiveGateway:
    @pytest.fixture
    def gateway(self, connected_data: FixtureData) -> LiveGateway:
        return LiveGateway(connected_data[0])

    async def test_leaderboard(self, gateway: LiveGateway):
        rows = await gateway.leaderboard("prj1")
        assert {row.username for row in rows} == {"user2", "user3"}
        assert [row.position for row in rows] == [1, 2]

    async def test_progress_details(self, gateway: LiveGateway):
        solved = await gateway.solved_secrets("user2", "prj1")
        assert isinstance(solved, list)
        submissions = await gateway.submission_log("user2", "prj1")
        assert isinstance(submissions, list)

    async def test_logs_with_mock_client_are_empty(self, gateway: LiveGateway):
        assert await gateway.project_cluster_logs("prj1") == ""
        assert await gateway.user_cluster_logs("user2", "prj1") == ""

    async def test_sessions_shapes(self, gateway: LiveGateway):
        rows = await gateway.user_sessions("user2")
        assert isinstance(rows, list)
        rows = await gateway.project_sessions("prj1")
        assert isinstance(rows, list)

    async def test_sessions_record_after_login_and_start(self, gateway: LiveGateway):
        ctf_app = gateway.ctf_app
        user = ctf_app.user_mgr.get_user("user2")
        ctf_app.user_mgr.record_login(user)
        rows = await gateway.user_sessions("user2")
        assert any(row.kind == "rendezvous" and row.state == "LOGIN" for row in rows)

    async def test_ssh_activity_empty_with_mock_client(self, gateway: LiveGateway):
        assert await gateway.ssh_activity("user2", "prj1") == []

    async def test_unknown_project_raises(self, gateway: LiveGateway):
        with pytest.raises(AdminError):
            await gateway.leaderboard("ghost")


class TestPreviewGateway:
    @pytest.fixture
    def gateway(self) -> PreviewGateway:
        return PreviewGateway(PreviewStore.with_sample_data())

    async def test_leaderboard_sorted_by_score(self, gateway: PreviewGateway):
        rows = await gateway.leaderboard("intro_linux")
        assert rows[0].username == "bob" and rows[0].position == 1

    async def test_solved_and_submissions(self, gateway: PreviewGateway):
        solved = await gateway.solved_secrets("alice", "intro_linux")
        assert solved and solved[0].name == "flag_web"
        submissions = await gateway.submission_log("alice", "intro_linux")
        assert len(submissions) == 2

    async def test_logs(self, gateway: PreviewGateway):
        text = await gateway.project_cluster_logs("intro_linux")
        assert "admin node ready" in text

    async def test_user_sessions_merges_kinds(self, gateway: PreviewGateway):
        rows = await gateway.user_sessions("alice")
        kinds = {row.kind for row in rows}
        assert kinds == {"rendezvous", "instance"}

    async def test_ssh_activity_parsed_from_logs(self, gateway: PreviewGateway):
        rows = await gateway.ssh_activity("alice", "intro_linux")
        states = [row.state for row in rows]
        assert "LOGIN" in states and "LOGOUT" in states


class TestSshParser:
    def test_patterns(self):
        text = (
            "x | Accepted publickey for carol from 10.0.0.1 port 2 ssh2\n"
            "x | Failed password for invalid user mallory from 10.0.0.9\n"
            "x | pam_unix(sshd:session): session closed for user carol\n"
            "x | some unrelated line\n"
        )
        rows = parse_ssh_activity("carol", text)
        assert [row.state for row in rows] == ["LOGIN", "FAILED", "LOGOUT"]
        assert all(row.kind == "ssh" for row in rows)
