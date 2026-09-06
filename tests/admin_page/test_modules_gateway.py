"""Module gateway tests over both implementations."""

import pytest

from fit_ctf_admin.core.live_gateway import LiveGateway
from fit_ctf_admin.core.preview_gateway import PreviewGateway
from fit_ctf_admin.core.preview_store import PreviewStore
from fit_ctf_admin.core.protocols import AdminGateway
from fit_ctf_admin.exceptions import AdminError


@pytest.fixture(params=["preview", "live"])
def gateway(request) -> AdminGateway:
    if request.param == "preview":
        return PreviewGateway(PreviewStore.with_sample_data())
    ctf_app, _ = request.getfixturevalue("empty_data")
    return LiveGateway(ctf_app)


async def test_list_modules_contains_bundled_template(gateway: AdminGateway):
    names = [module.name for module in await gateway.list_modules()]
    assert "template" in names


async def test_create_and_delete_module(gateway: AdminGateway):
    await gateway.create_module("fresh_mod")
    names = [module.name for module in await gateway.list_modules()]
    assert "fresh_mod" in names
    await gateway.remove_module("fresh_mod")
    names = [module.name for module in await gateway.list_modules()]
    assert "fresh_mod" not in names


async def test_create_duplicate_module_raises(gateway: AdminGateway):
    await gateway.create_module("fresh_mod")
    with pytest.raises(AdminError):
        await gateway.create_module("fresh_mod")


async def test_build_module_succeeds_with_mock_client(gateway: AdminGateway):
    await gateway.build_module("template")


async def test_remove_used_module_raises_in_preview():
    gateway = PreviewGateway(PreviewStore.with_sample_data())
    with pytest.raises(AdminError):
        await gateway.remove_module("ssh_ubi")  # sample data marks it referenced
