import pytest

from fit_ctf_utils.exceptions import (
    ContainerPortUsageCollisionException,
    ForwardedPortUsageCollisionException,
    MaxUserCountReachedException,
    ProjectNotExistException,
    SSHPortOutOfRangeException,
    UserEnrolledToProjectException,
    UserNotEnrolledToProjectException,
    UserNotExistsException,
)
from tests import FixtureData


def test_user_is_enrolled_to_the_project(
    connected_data: FixtureData,
):
    ctf_mgr, _ = connected_data
    user_enrollment_mgr = ctf_mgr.user_enrollment_mgr
    user_mgr = ctf_mgr.user_mgr
    prj_mgr = ctf_mgr.prj_mgr

    # fill mgr with data
    assert not user_enrollment_mgr.user_is_enrolled_to_project(
        user_mgr.get_user("user1"), prj_mgr.get_project("prj1")
    )
    assert not user_enrollment_mgr.user_is_enrolled_to_project(
        user_mgr.get_user("user3"), prj_mgr.get_project("prj2")
    )

    assert user_enrollment_mgr.user_is_enrolled_to_project(
        user_mgr.get_user("user1"), prj_mgr.get_project("prj2")
    )
    assert user_enrollment_mgr.user_is_enrolled_to_project(
        user_mgr.get_user("user2"), prj_mgr.get_project("prj1")
    )
    assert user_enrollment_mgr.user_is_enrolled_to_project(
        user_mgr.get_user("user2"), prj_mgr.get_project("prj2")
    )
    assert user_enrollment_mgr.user_is_enrolled_to_project(
        user_mgr.get_user("user3"), prj_mgr.get_project("prj1")
    )


def test_get_user_enrollment(
    connected_data: FixtureData,
):
    ctf_mgr, _ = connected_data
    user_enrollment_mgr = ctf_mgr.user_enrollment_mgr

    user_enrollment_mgr = ctf_mgr.user_enrollment_mgr
    user_mgr = ctf_mgr.user_mgr
    prj_mgr = ctf_mgr.prj_mgr

    # fill mgr with data
    with pytest.raises(UserNotEnrolledToProjectException):
        user_enrollment_mgr.get_user_enrollment(
            user_mgr.get_user("user1"), prj_mgr.get_project("prj1")
        )

    ue = user_enrollment_mgr.get_user_enrollment(
        user_mgr.get_user("user1"), prj_mgr.get_project("prj2")
    )

    assert (
        ue.active
        and ue.user_id.id == user_mgr.get_user("user1").id
        and ue.project_id.id == prj_mgr.get_project("prj2").id
    )


def test_compose_file(connected_data: FixtureData):
    ctf_mgr, _ = connected_data
    ue_mgr = ctf_mgr.user_enrollment_mgr

    with pytest.raises(UserNotEnrolledToProjectException):
        ue_mgr.get_compose_file("user1", "prj1")

    path = ctf_mgr._paths["projects"] / "prj1" / "users" / "user2_compose.yaml"
    assert not path.exists()

    compose_path = ue_mgr.get_compose_file("user2", "prj1")
    assert str(compose_path.resolve()) == str(path.resolve())
    assert path.exists()


def test_enroll_user_to_project(
    connected_data: FixtureData,
):
    ctf_mgr, _ = connected_data
    ue_mgr = ctf_mgr.user_enrollment_mgr
    prj_mgr = ctf_mgr.prj_mgr
    user_mgr = ctf_mgr.user_mgr

    with pytest.raises(UserNotExistsException):
        ue_mgr.enroll_user_to_project("new_user", "prj1")

    with pytest.raises(ProjectNotExistException):
        ue_mgr.enroll_user_to_project("user1", "project")

    with pytest.raises(UserEnrolledToProjectException):
        ue_mgr.enroll_user_to_project("user2", "prj1")

    with pytest.raises(ContainerPortUsageCollisionException):
        ue_mgr.enroll_user_to_project(
            "user1",
            "prj1",
            container_port=prj_mgr.get_project("prj1").starting_port_bind,
        )
    with pytest.raises(SSHPortOutOfRangeException):
        ue_mgr.enroll_user_to_project(
            "user1",
            "prj1",
            container_port=prj_mgr.get_project("prj1").starting_port_bind + 100,
        )
    with pytest.raises(SSHPortOutOfRangeException):
        ue_mgr.enroll_user_to_project(
            "user1",
            "prj1",
            forwarded_port=70000,
        )
    with pytest.raises(ForwardedPortUsageCollisionException):
        ue_mgr.enroll_user_to_project(
            "user1",
            "prj1",
            forwarded_port=prj_mgr.get_project("prj1").starting_port_bind,
        )

    assert len(ue_mgr.get_user_enrollments_for_project("prj1")) == 2
    ue = ue_mgr.enroll_user_to_project("user1", "prj1")
    assert ue and len(ue_mgr.get_user_enrollments_for_project("prj1")) == 3
    assert len(ue.services) > 0

    user_mgr.create_new_user("user4", "StrongPassword")
    assert user_mgr
    with pytest.raises(MaxUserCountReachedException):
        ue_mgr.enroll_user_to_project("user4", "prj1")


def test_enroll_multiple_users_to_project(
    unconnected_data: FixtureData,
):
    ctf_mgr, _ = unconnected_data
    ue_mgr = ctf_mgr.user_enrollment_mgr
    user_mgr = ctf_mgr.user_mgr

    new_usernames = ["user4", "user5"]
    user_mgr.create_multiple_users(new_usernames, "userPassw0rd")
    new_users = user_mgr.get_docs(username={"$in": new_usernames}, active=True)

    with pytest.raises(MaxUserCountReachedException):
        ue_mgr.enroll_multiple_users_to_project(
            [f"user{i+1}" for i in range(5)], "prj1"
        )

    assert len(ue_mgr.get_user_enrollments_for_project("prj1")) == 0
    ucs = ue_mgr.enroll_multiple_users_to_project(new_usernames, "prj1")
    assert len(ucs) == len(new_usernames)
    assert len(ucs) == len(ue_mgr.get_user_enrollments_for_project("prj1"))

    assert set([uc.user_id.id for uc in ucs]) == set([u.id for u in new_users])
    ucs = ue_mgr.enroll_multiple_users_to_project(
        [f"user{i+3}" for i in range(3)], "prj1"
    )

    assert len(ucs) == 1
    assert set([u.user_id.id for u in ucs]).difference(set([u.id for u in new_users]))


def test_get_enrollments_info(connected_data: FixtureData):
    ctf_mgr, _ = connected_data
    ue_mgr = ctf_mgr.user_enrollment_mgr
    prj_mgr = ctf_mgr.prj_mgr
    user_mgr = ctf_mgr.user_mgr

    user1 = user_mgr.get_user("user1")
    user2 = user_mgr.get_user("user2")
    prj1 = prj_mgr.get_project("prj1")

    user_in_prj = ue_mgr.get_user_enrollments_for_project(prj1)
    user_ids_in_prj = [u.id for u in user_in_prj]
    assert (
        len(user_ids_in_prj) == 2
        and user1.id not in user_ids_in_prj
        and user2.id in user_ids_in_prj
    )
    assert set([u.username for u in user_in_prj]) == set(
        [u["username"] for u in ue_mgr.get_user_enrollments_for_project_raw(prj1)]
    )

    assert (
        len(ue_mgr.get_enrolled_projects(user1)) == 1
        and len(ue_mgr.get_enrolled_projects(user2)) == 2
    )

    assert (
        len(ue_mgr.get_enrolled_projects_raw(user1)) == 1
        and len(ue_mgr.get_enrolled_projects_raw(user2)) == 2
    )

    prj_mgr.disable_project(prj1)
    all_prjs = ue_mgr.get_all_enrolled_projects_raw(user2)
    assert len(all_prjs) == 2 and len([p for p in all_prjs if p["active"]]) == 1


def test_disable_enrollment(connected_data: FixtureData):
    ctf_mgr, _ = connected_data
    ue_mgr = ctf_mgr.user_enrollment_mgr
    prj_mgr = ctf_mgr.prj_mgr
    user_mgr = ctf_mgr.user_mgr

    user1 = user_mgr.get_user("user1")
    user2 = user_mgr.get_user("user2")
    prj1 = prj_mgr.get_project("prj1")

    with pytest.raises(UserNotEnrolledToProjectException):
        ue_mgr.disable_enrollment(user1, prj1)

    ue_mgr.disable_enrollment(user2, prj1)
    with pytest.raises(UserNotEnrolledToProjectException):
        ue_mgr.get_user_enrollment(user2, prj1)
    assert len(ue_mgr.get_user_enrollments_for_project(prj1)) == 1


def test_disable_multiple_enrollments(connected_data: FixtureData):
    ctf_mgr, _ = connected_data
    ue_mgr = ctf_mgr.user_enrollment_mgr
    prj_mgr = ctf_mgr.prj_mgr
    user_mgr = ctf_mgr.user_mgr

    user1 = user_mgr.get_user("user1")
    user2 = user_mgr.get_user("user2")
    user3 = user_mgr.get_user("user3")
    prj1 = prj_mgr.get_project("prj1")
    prj2 = prj_mgr.get_project("prj2")

    with pytest.raises(UserNotEnrolledToProjectException):
        ue_mgr.disable_enrollment(user1, prj1)

    assert len(ue_mgr.get_docs(active=True)) == 4
    ue_mgr.disable_multiple_enrollments([(user2, prj1), (user2, prj2), (user3, prj1)])

    assert len(ue_mgr.get_docs()) == 4
    assert len(ue_mgr.get_docs(active=True)) == 1


def test_flush_enrollment(connected_data: FixtureData):
    ctf_mgr, _ = connected_data
    ue_mgr = ctf_mgr.user_enrollment_mgr
    prj_mgr = ctf_mgr.prj_mgr
    user_mgr = ctf_mgr.user_mgr

    user2 = user_mgr.get_user("user2")
    prj1 = prj_mgr.get_project("prj1")

    with pytest.raises(UserEnrolledToProjectException):
        ue_mgr.flush_enrollment(user2, prj1)

    ue_mgr.compile_compose_file(user2, prj1)
    path = (
        ctf_mgr._paths["projects"]
        / prj1.name
        / "users"
        / f"{user2.username}_compose.yaml"
    )
    assert path.exists()
    ue_mgr.disable_enrollment(user2, prj1)
    assert path.exists()
    ue_mgr.flush_enrollment(user2, prj1)
    assert not ue_mgr.get_doc_by_filter(
        **{"user_id.$id": user2.id, "project_id.$id": prj1.id}
    )
    assert not path.exists()


def test_flush_multiple_enrollments(connected_data: FixtureData):
    ctf_mgr, _ = connected_data
    ue_mgr = ctf_mgr.user_enrollment_mgr
    prj_mgr = ctf_mgr.prj_mgr
    user_mgr = ctf_mgr.user_mgr

    user1 = user_mgr.get_user("user1")
    user2 = user_mgr.get_user("user2")
    user3 = user_mgr.get_user("user3")
    prj1 = prj_mgr.get_project("prj1")
    prj2 = prj_mgr.get_project("prj2")
    assert len(ue_mgr.get_docs()) == 4
    pairs = [(user2, prj1), (user2, prj2), (user3, prj1)]
    ue_mgr.flush_multiple_enrollments(pairs)
    assert len(ue_mgr.get_docs()) == 4
    for u, p in pairs:
        ue_mgr.compile_compose_file(u, p)

    pairs.append((user1, prj1))
    assert (
        len([f for f in (ctf_mgr._paths["projects"] / prj1.name / "users").iterdir()])
        == 2
    )
    ue_mgr.disable_multiple_enrollments(pairs)
    ue_mgr.flush_multiple_enrollments(pairs)
    assert len(ue_mgr.get_docs()) == 1
    assert not len(
        [f for f in (ctf_mgr._paths["projects"] / prj1.name / "users").iterdir()]
    )


def test_cancel_user_enrollment(connected_data: FixtureData):
    ctf_mgr, _ = connected_data
    ue_mgr = ctf_mgr.user_enrollment_mgr
    prj_mgr = ctf_mgr.prj_mgr
    user_mgr = ctf_mgr.user_mgr

    user1 = user_mgr.get_user("user1")
    prj2 = prj_mgr.get_project("prj2")

    ue_mgr.compile_compose_file(user1, prj2)
    filepath = (
        ctf_mgr._paths["projects"]
        / prj2.name
        / "users"
        / f"{user1.username}_compose.yaml"
    )
    assert filepath.exists()
    assert len(ue_mgr.get_user_enrollments_for_project(prj2)) == 2

    ue_mgr.cancel_user_enrollment(user1, prj2)
    assert not ue_mgr.get_doc_by_filter(
        **{"user_id.$id": user1.id, "project_id.$id": prj2.id}
    )
    assert not filepath.exists()
    assert len(ue_mgr.get_user_enrollments_for_project(prj2)) == 1


def test_cancel_multiple_enrollments(connected_data: FixtureData):
    ctf_mgr, _ = connected_data
    ue_mgr = ctf_mgr.user_enrollment_mgr
    prj_mgr = ctf_mgr.prj_mgr

    prj1 = prj_mgr.get_project("prj1")
    assert len(ue_mgr.get_user_enrollments_for_project(prj1)) == 2
    ue_mgr.cancel_multiple_enrollments([f"user{i+1}" for i in range(3)], prj1)
    assert len(ue_mgr.get_user_enrollments_for_project(prj1)) == 0


def test_cancel_all_project_enrollments(connected_data: FixtureData):
    ctf_mgr, _ = connected_data
    ue_mgr = ctf_mgr.user_enrollment_mgr
    prj_mgr = ctf_mgr.prj_mgr

    prj1 = prj_mgr.get_project("prj1")
    assert len(ue_mgr.get_user_enrollments_for_project(prj1)) == 2
    ue_mgr.cancel_all_project_enrollments(prj1)
    assert len(ue_mgr.get_user_enrollments_for_project(prj1)) == 0


def test_cancel_user_from_all_projects(connected_data: FixtureData):
    ctf_mgr, _ = connected_data
    ue_mgr = ctf_mgr.user_enrollment_mgr
    user_mgr = ctf_mgr.user_mgr

    user2 = user_mgr.get_user("user2")
    assert len(ue_mgr.get_enrolled_projects(user2)) == 2
    ue_mgr.cancel_user_from_all_projects(user2)
    assert len(ue_mgr.get_enrolled_projects(user2)) == 0


def test_delete_all(connected_data: FixtureData):
    ctf_mgr, _ = connected_data
    ue_mgr = ctf_mgr.user_enrollment_mgr

    assert len(ue_mgr.get_docs()) == 4
    ue_mgr.delete_all()
    assert not ue_mgr.get_docs()
