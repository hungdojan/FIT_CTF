from typing import TypeAlias

import pytest

from fit_ctf_backend.ctf_manager import CTFManager
from fit_ctf_models.cluster import ClusterConfig, ClusterConfigManager, Service
from fit_ctf_utils.exceptions import ServiceExistException, ServiceNotExistException
from tests import FixtureData

ServiceManagers: TypeAlias = tuple[ClusterConfigManager, CTFManager, str]


@pytest.fixture(params=["project", "user"])
def service_mgrs(
    request: pytest.FixtureRequest, connected_data: FixtureData
) -> ServiceManagers:
    ctf_mgr, _ = connected_data
    if request.param == "project":
        mgr = ctf_mgr.prj_mgr
    else:
        mgr = ctf_mgr.user_enrollment_mgr

    return mgr, ctf_mgr, request.param


def test_base_services(service_mgrs: ServiceManagers):
    mgr, ctf_mgr, param = service_mgrs
    if param == "project":
        for prj in ctf_mgr.prj_mgr.get_docs():
            services = mgr.list_services(prj)
            assert len(services.keys()) == 1
            assert services.get("admin")
            assert services["admin"].module_name == "base"
    elif param == "user":
        for user_enroll in ctf_mgr.user_enrollment_mgr.get_docs():
            services = mgr.list_services(user_enroll)
            assert len(services.keys()) == 1
            assert services.get("login")
            assert services["login"].module_name == "base_ssh"


def test_register_service(service_mgrs: ServiceManagers):
    mgr, _, _ = service_mgrs

    docs = mgr.get_docs()
    assert docs
    doc: ClusterConfig = docs[0]
    assert len(mgr.list_services(doc)) == 1

    mgr.register_service(
        doc, "new_service", Service(service_name="new_service", module_name="base")
    )

    updated_doc: ClusterConfig | None = mgr.get_doc_by_id(doc.id)
    assert updated_doc and len(updated_doc.services.keys()) == 2

    with pytest.raises(ServiceExistException):
        mgr.register_service(
            doc,
            "new_service",
            Service(service_name="new_service", module_name="base_ssh"),
        )


def test_get_service(service_mgrs: ServiceManagers):
    mgr, _, param = service_mgrs
    docs = mgr.get_docs()
    assert docs
    doc: ClusterConfig = docs[0]

    if param == "project":
        service = mgr.get_service(doc, "admin")
        assert service.module_name == "base"
        assert service.service_name == "admin"
        assert not service.ports
        assert not service.env
        assert not service.volumes
        assert service.is_local
        assert len(service.networks.keys()) > 0

    elif param == "user":
        service = mgr.get_service(doc, "login")
        assert service.module_name == "base_ssh"
        assert service.service_name == "login"
        assert len(service.ports) == 1
        assert not service.env
        assert len(service.volumes) == 2
        assert service.is_local
        assert len(service.networks.keys()) == 2

    with pytest.raises(ServiceNotExistException):
        mgr.get_service(doc, "unknown")


def test_list_services(service_mgrs: ServiceManagers):
    mgr, _, _ = service_mgrs

    docs = mgr.get_docs()
    assert docs
    doc: ClusterConfig = docs[0]
    assert len(mgr.list_services(doc)) == 1

    mgr.register_service(
        doc, "new_service", Service(service_name="new_service", module_name="base")
    )

    updated_doc: ClusterConfig | None = mgr.get_doc_by_id(doc.id)
    assert updated_doc

    assert len(mgr.list_services(updated_doc)) == 2
    assert mgr.list_services(updated_doc).get("new_service")


def test_update_service(service_mgrs: ServiceManagers):
    mgr, _, _ = service_mgrs

    docs = mgr.get_docs()
    assert docs
    doc: ClusterConfig = docs[0]

    mgr.register_service(
        doc, "new_service", Service(service_name="new_service", module_name="base")
    )

    service = mgr.get_service(doc, "new_service")
    assert not service.env
    assert not service.ports
    assert not service.networks

    service.ports.extend(["18080:8080", "18443:8443"])
    service.env.extend(["ENV1=1", "ENV2=2"])
    service.networks.update({"network1": {}, "network2": {}})

    mgr.update_service(doc, "new_service", service)
    updated_doc = mgr.get_doc_by_id(doc.id)
    assert updated_doc

    assert len(mgr.list_services(updated_doc)) == 2
    service = mgr.get_service(updated_doc, "new_service")
    assert len(service.env) == 2
    assert len(service.ports) == 2
    assert not service.volumes
    assert set(service.networks.keys()) == {"network1", "network2"}

    with pytest.raises(ServiceNotExistException):
        mgr.update_service(updated_doc, "unknown", service)


def test_remove_service(service_mgrs: ServiceManagers):
    mgr, _, _ = service_mgrs

    docs = mgr.get_docs()
    assert docs
    doc: ClusterConfig = docs[0]
    services = list(mgr.list_services(doc).values())
    assert len(services) == 1

    assert not mgr.remove_service(doc, "unknown")

    mgr.remove_service(doc, services[0].service_name)
    assert not mgr.list_services(mgr.get_doc_by_id(doc.id))
