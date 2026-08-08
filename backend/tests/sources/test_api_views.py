import pytest
from rest_framework.test import APIClient

from core.factories import MembershipFactory, WorkspaceFactory
from ingestion.factories import ChunkFactory
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


def test_list_sources_reports_indexing_progress() -> None:
    """status="ready" only means the sync finished — embedding runs after
    it, in a separate task. These counts are what lets a client tell
    "indexed and queryable" apart from "synced, still embedding".
    """
    membership = MembershipFactory()
    source = SourceFactory(workspace=membership.workspace)
    document = DocumentFactory(source=source)
    ChunkFactory(document=document, embedding=[0.0] * 1024)
    ChunkFactory(document=document, embedding=None)
    ChunkFactory(document=document, embedding=None)

    response = _authed_client(membership.user).get("/api/sources/")

    assert response.status_code == 200
    item = response.json()["results"][0]
    assert item["chunk_count"] == 3
    assert item["embedded_chunk_count"] == 1


def test_source_with_no_documents_reports_zero_chunks() -> None:
    membership = MembershipFactory()
    SourceFactory(workspace=membership.workspace)

    response = _authed_client(membership.user).get("/api/sources/")

    item = response.json()["results"][0]
    assert item["chunk_count"] == 0
    assert item["embedded_chunk_count"] == 0


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


def test_create_source_accepts_a_valid_section_boundary_pattern() -> None:
    membership = MembershipFactory()

    response = _authed_client(membership.user).post(
        "/api/sources/",
        {
            "workspace": str(membership.workspace.id),
            "name": "Journal",
            "type": Source.SourceType.LOCAL_FOLDER,
            "config": {
                "path": "/app/storage/journal",
                "section_boundary_pattern": r"^\d{4}-\d{2}-\d{2}",
            },
        },
        format="json",
    )

    assert response.status_code == 201


def test_create_source_rejects_an_invalid_section_boundary_pattern() -> None:
    membership = MembershipFactory()

    response = _authed_client(membership.user).post(
        "/api/sources/",
        {
            "workspace": str(membership.workspace.id),
            "name": "Journal",
            "type": Source.SourceType.LOCAL_FOLDER,
            "config": {"path": "/app/storage/journal", "section_boundary_pattern": "("},
        },
        format="json",
    )

    assert response.status_code == 400
    assert "section_boundary_pattern" in response.json()["config"]


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


def test_browse_lists_directories_under_media_root(settings, tmp_path) -> None:
    settings.MEDIA_ROOT = str(tmp_path)
    (tmp_path / "notes").mkdir()
    membership = MembershipFactory()

    response = _authed_client(membership.user).get("/api/sources/browse/")

    assert response.status_code == 200
    body = response.json()
    assert body["path"] == ""
    assert [entry["name"] for entry in body["entries"]] == ["notes"]
    assert body["entries"][0]["absolute_path"] == str(tmp_path / "notes")


def test_browse_rejects_path_traversal(settings, tmp_path) -> None:
    settings.MEDIA_ROOT = str(tmp_path)
    membership = MembershipFactory()

    response = _authed_client(membership.user).get("/api/sources/browse/", {"path": "../../etc"})

    assert response.status_code == 400


def test_browse_requires_authentication(settings, tmp_path) -> None:
    settings.MEDIA_ROOT = str(tmp_path)

    response = APIClient().get("/api/sources/browse/")

    assert response.status_code in (401, 403)


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
