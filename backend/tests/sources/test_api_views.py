import pytest
from rest_framework.test import APIClient

from core.factories import MembershipFactory, WorkspaceFactory
from sources.factories import DocumentFactory, SourceFactory
from sources.models import Source

pytestmark = pytest.mark.django_db


def _authed_client(user) -> APIClient:
    client = APIClient()
    client.force_login(user)
    return client


def test_list_sources_returns_only_own_workspace() -> None:
    membership = MembershipFactory()
    own_source = SourceFactory(workspace=membership.workspace)
    SourceFactory()  # different workspace, must not appear

    response = _authed_client(membership.user).get("/api/sources/")

    assert response.status_code == 200
    ids = [item["id"] for item in response.json()["results"]]
    assert ids == [str(own_source.id)]


def test_cannot_retrieve_source_from_another_workspace() -> None:
    membership = MembershipFactory()
    other_source = SourceFactory()

    response = _authed_client(membership.user).get(f"/api/sources/{other_source.id}/")

    assert response.status_code == 404


def test_create_source_rejects_a_workspace_the_user_is_not_a_member_of() -> None:
    membership = MembershipFactory()
    other_workspace = WorkspaceFactory()

    response = _authed_client(membership.user).post(
        "/api/sources/",
        {
            "workspace": str(other_workspace.id),
            "name": "Notes",
            "type": Source.SourceType.LOCAL_FOLDER,
        },
        format="json",
    )

    assert response.status_code == 400
    assert not Source.objects.filter(workspace=other_workspace).exists()


def test_create_source_in_own_workspace_succeeds() -> None:
    membership = MembershipFactory()

    response = _authed_client(membership.user).post(
        "/api/sources/",
        {
            "workspace": str(membership.workspace.id),
            "name": "Notes",
            "type": Source.SourceType.LOCAL_FOLDER,
        },
        format="json",
    )

    assert response.status_code == 201
    assert Source.objects.filter(workspace=membership.workspace, name="Notes").exists()


def test_sync_action_queues_the_celery_task(monkeypatch) -> None:
    membership = MembershipFactory()
    source = SourceFactory(workspace=membership.workspace)
    queued_ids = []
    monkeypatch.setattr(
        "sources.views.sync_source_task.delay", lambda source_id: queued_ids.append(source_id)
    )

    response = _authed_client(membership.user).post(f"/api/sources/{source.id}/sync/")

    assert response.status_code == 202
    assert queued_ids == [str(source.id)]


def test_sync_action_on_another_workspaces_source_is_not_found(monkeypatch) -> None:
    membership = MembershipFactory()
    other_source = SourceFactory()
    monkeypatch.setattr("sources.views.sync_source_task.delay", lambda source_id: None)

    response = _authed_client(membership.user).post(f"/api/sources/{other_source.id}/sync/")

    assert response.status_code == 404


def test_unauthenticated_request_is_rejected() -> None:
    response = APIClient().get("/api/sources/")

    assert response.status_code in (401, 403)


def test_documents_are_scoped_to_the_users_workspace() -> None:
    membership = MembershipFactory()
    own_document = DocumentFactory(source__workspace=membership.workspace)
    DocumentFactory()  # different workspace, must not appear

    response = _authed_client(membership.user).get("/api/documents/")

    assert response.status_code == 200
    ids = [item["id"] for item in response.json()["results"]]
    assert ids == [str(own_document.id)]


def test_documents_endpoint_is_read_only() -> None:
    membership = MembershipFactory()

    response = _authed_client(membership.user).post("/api/documents/", {}, format="json")

    assert response.status_code == 405
