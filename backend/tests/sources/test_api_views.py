import pytest
from rest_framework.test import APIClient

from core.factories import MembershipFactory, WorkspaceFactory
from ingestion.factories import ChunkFactory
from sources.factories import DocumentFactory, SourceFactory
from sources.locking import is_cancel_requested
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


def test_cancel_sync_flags_a_source_that_is_syncing() -> None:
    membership = MembershipFactory()
    source = SourceFactory(workspace=membership.workspace, status=Source.Status.SYNCING)

    response = _authed_client(membership.user).post(f"/api/sources/{source.id}/cancel_sync/")

    assert response.status_code == 202
    assert is_cancel_requested(source.id) is True


def test_cancel_sync_on_a_source_that_is_not_syncing_is_rejected() -> None:
    membership = MembershipFactory()
    source = SourceFactory(workspace=membership.workspace, status=Source.Status.READY)

    response = _authed_client(membership.user).post(f"/api/sources/{source.id}/cancel_sync/")

    assert response.status_code == 409
    assert is_cancel_requested(source.id) is False


def test_cancel_sync_on_another_workspaces_source_is_not_found() -> None:
    membership = MembershipFactory()
    other_source = SourceFactory(status=Source.Status.SYNCING)

    response = _authed_client(membership.user).post(f"/api/sources/{other_source.id}/cancel_sync/")

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


def test_deleted_documents_are_excluded() -> None:
    membership = MembershipFactory()
    live_document = DocumentFactory(source__workspace=membership.workspace)
    DocumentFactory(source__workspace=membership.workspace, deleted=True)

    response = _authed_client(membership.user).get("/api/documents/")

    assert response.status_code == 200
    ids = [item["id"] for item in response.json()["results"]]
    assert ids == [str(live_document.id)]


def test_documents_endpoint_is_read_only() -> None:
    membership = MembershipFactory()

    response = _authed_client(membership.user).post("/api/documents/", {}, format="json")

    assert response.status_code == 405


def test_document_chunks_returns_the_indexed_form_in_order() -> None:
    membership = MembershipFactory()
    document = DocumentFactory(source__workspace=membership.workspace)
    ChunkFactory(document=document, index=1, content="second", heading_path="A > B")
    ChunkFactory(document=document, index=0, content="first", heading_path="A")

    response = _authed_client(membership.user).get(f"/api/documents/{document.id}/chunks/")

    assert response.status_code == 200
    body = response.json()["results"]
    assert [chunk["index"] for chunk in body] == [0, 1]
    assert body[0]["content"] == "first"
    # The heading-prefixed form is what actually gets embedded, so the
    # browser has to be able to show both.
    assert body[1]["content_with_heading"] == "A > B\n\nsecond"


def test_document_chunks_reports_embedding_state_without_the_vector() -> None:
    membership = MembershipFactory()
    document = DocumentFactory(source__workspace=membership.workspace)
    ChunkFactory(document=document, index=0, embedding=[0.0] * 1024)
    ChunkFactory(document=document, index=1, embedding=None)

    body = (
        _authed_client(membership.user)
        .get(f"/api/documents/{document.id}/chunks/")
        .json()["results"]
    )

    assert [chunk["embedded"] for chunk in body] == [True, False]
    assert "embedding" not in body[0]


def test_cannot_read_chunks_of_another_workspaces_document() -> None:
    """The one that matters: this endpoint returns note text verbatim."""
    membership = MembershipFactory()
    other_document = DocumentFactory()
    ChunkFactory(document=other_document, index=0, content="private")

    response = _authed_client(membership.user).get(f"/api/documents/{other_document.id}/chunks/")

    assert response.status_code == 404


def test_documents_report_their_chunk_counts() -> None:
    membership = MembershipFactory()
    document = DocumentFactory(source__workspace=membership.workspace)
    ChunkFactory(document=document, index=0, embedding=[0.0] * 1024)
    ChunkFactory(document=document, index=1, embedding=None)

    body = _authed_client(membership.user).get("/api/documents/").json()

    item = next(d for d in body["results"] if d["id"] == str(document.id))
    assert item["chunk_count"] == 2
    assert item["embedded_chunk_count"] == 1


def test_document_chunks_are_paginated() -> None:
    """The biggest real document splits into hundreds of chunks, each
    carrying its whole text — one unpaginated response would be several
    megabytes.
    """
    membership = MembershipFactory()
    document = DocumentFactory(source__workspace=membership.workspace)
    for index in range(30):
        ChunkFactory(document=document, index=index)

    body = _authed_client(membership.user).get(f"/api/documents/{document.id}/chunks/").json()

    assert body["count"] == 30
    assert len(body["results"]) == 25
    assert body["next"] is not None
