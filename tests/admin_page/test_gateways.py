"""Protocol-conformance tests run against both gateway implementations.

The same behavioral tests execute over the in-memory preview gateway and the
live gateway (real test MongoDB, ``CONTAINER_CLIENT=mock``), which is the
point of the shared protocol: pages cannot tell the two apart.
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


async def _make_user(gateway: AdminGateway, username: str = "user_a") -> str:
    row, password = await gateway.create_user(username, STRONG_PASSWORD, generate_password=False)
    assert row.username == username
    return password


async def _make_project(gateway: AdminGateway, name: str = "prj_a", capacity: int = 5):
    return await gateway.create_project(name, capacity)


class TestUsers:
    async def test_create_and_list(self, gateway: AdminGateway):
        await _make_user(gateway)
        users = await gateway.list_users()
        assert [user.username for user in users] == ["user_a"]
        assert users[0].active

    async def test_generated_password_is_returned(self, gateway: AdminGateway):
        _, password = await gateway.create_user("user_b", None, generate_password=True)
        assert len(password) >= 10

    async def test_duplicate_username_raises(self, gateway: AdminGateway):
        await _make_user(gateway)
        with pytest.raises(AdminError):
            await _make_user(gateway)

    async def test_empty_username_raises(self, gateway: AdminGateway):
        with pytest.raises(AdminError):
            await gateway.create_user("   ", STRONG_PASSWORD, generate_password=False)

    async def test_missing_password_raises(self, gateway: AdminGateway):
        with pytest.raises(AdminError):
            await gateway.create_user("user_c", None, generate_password=False)

    async def test_weak_password_raises(self, gateway: AdminGateway):
        with pytest.raises(AdminError):
            await gateway.create_user("user_d", "weak", generate_password=False)

    async def test_delete_user(self, gateway: AdminGateway):
        await _make_user(gateway)
        await gateway.delete_user("user_a")
        assert await gateway.list_users(include_inactive=True) == []

    async def test_disable_user(self, gateway: AdminGateway):
        await _make_user(gateway)
        await gateway.disable_user("user_a")
        assert await gateway.list_users() == []
        users = await gateway.list_users(include_inactive=True)
        assert len(users) == 1 and not users[0].active


class TestProjects:
    async def test_create_and_list(self, gateway: AdminGateway):
        row = await _make_project(gateway)
        assert row.name == "prj_a" and row.active_users == 0
        projects = await gateway.list_projects()
        assert [project.name for project in projects] == ["prj_a"]

    async def test_duplicate_project_raises(self, gateway: AdminGateway):
        await _make_project(gateway)
        with pytest.raises(AdminError):
            await _make_project(gateway)

    async def test_invalid_capacity_raises(self, gateway: AdminGateway):
        with pytest.raises(AdminError):
            await gateway.create_project("prj_bad", 0)

    async def test_delete_project(self, gateway: AdminGateway):
        await _make_project(gateway)
        await gateway.delete_project("prj_a")
        assert await gateway.list_projects(include_inactive=True) == []

    async def test_reserved_ports(self, gateway: AdminGateway):
        await gateway.create_project("prj_a", 5, starting_port_bind=10_000)
        ports = await gateway.reserved_ports()
        assert len(ports) == 1
        assert ports[0].project == "prj_a"
        assert ports[0].min_port == 10_000


class TestEnrollments:
    async def _setup(self, gateway: AdminGateway) -> None:
        await _make_user(gateway, "user_a")
        await _make_user(gateway, "user_b")
        await _make_project(gateway, "prj_a", capacity=1)

    async def test_enroll_and_list(self, gateway: AdminGateway):
        await self._setup(gateway)
        row = await gateway.enroll_user("user_a", "prj_a")
        assert (row.username, row.project, row.active) == ("user_a", "prj_a", True)
        rows = await gateway.list_enrollments("prj_a")
        assert [r.username for r in rows] == ["user_a"]
        all_rows = await gateway.list_all_enrollments()
        assert [(r.username, r.project) for r in all_rows] == [("user_a", "prj_a")]

    async def test_enrollable_users_shrinks(self, gateway: AdminGateway):
        await self._setup(gateway)
        assert await gateway.enrollable_users("prj_a") == ["user_a", "user_b"]
        await gateway.enroll_user("user_a", "prj_a")
        assert await gateway.enrollable_users("prj_a") == ["user_b"]

    async def test_duplicate_enrollment_raises(self, gateway: AdminGateway):
        await self._setup(gateway)
        await gateway.enroll_user("user_a", "prj_a")
        with pytest.raises(AdminError):
            await gateway.enroll_user("user_a", "prj_a")

    async def test_capacity_limit_raises(self, gateway: AdminGateway):
        await self._setup(gateway)
        await gateway.enroll_user("user_a", "prj_a")
        with pytest.raises(AdminError):
            await gateway.enroll_user("user_b", "prj_a")

    async def test_cancel_enrollment(self, gateway: AdminGateway):
        await self._setup(gateway)
        await gateway.enroll_user("user_a", "prj_a")
        await gateway.cancel_enrollment("user_a", "prj_a")
        assert await gateway.list_enrollments("prj_a") == []

    async def test_enroll_unknown_user_raises(self, gateway: AdminGateway):
        await _make_project(gateway, "prj_a")
        with pytest.raises(AdminError):
            await gateway.enroll_user("ghost", "prj_a")


class TestErrorMapping:
    async def test_admin_error_is_a_plain_exception(self, gateway: AdminGateway):
        """Domain errors must surface as Exception subclasses.

        ``CTFBaseException`` derives from ``BaseException``; the gateway must
        map it so generic ``except Exception`` handlers (and Textual workers)
        can deal with it.
        """
        with pytest.raises(AdminError) as excinfo:
            await gateway.list_enrollments("does_not_exist")
        assert isinstance(excinfo.value, Exception)


class TestPreviewSampleData:
    async def test_sample_data_is_consistent(self):
        gateway = PreviewGateway(PreviewStore.with_sample_data())
        users = await gateway.list_users(include_inactive=True)
        assert len(users) == 4
        projects = await gateway.list_projects(include_inactive=True)
        assert len(projects) == 3
        enrollments = await gateway.list_all_enrollments()
        assert len(enrollments) == 4
        alice = next(user for user in users if user.username == "alice")
        assert alice.projects == ("intro_linux", "web_exploitation")
