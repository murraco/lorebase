from contextlib import contextmanager
from unittest.mock import patch

import pytest
from mcp.server.auth.middleware.auth_context import auth_context_var
from mcp.server.auth.middleware.bearer_auth import AuthenticatedUser
from mcp.server.auth.provider import AccessToken

from core.factories import MembershipFactory
from ingestion.factories import ChunkFactory
from mcp_server.tools import get_document, list_sources, search_knowledge
from rag.retrieval.base import RetrievalResult
from sources.factories import DocumentFactory, SourceFactory

pytestmark = pytest.mark.django_db


class _StubRetriever:
    def __init__(self, results):
        self._results = results
        self.last_call = None

    def search(self, query, *, workspace_id, top_k=10, filters=None):
        self.last_call = {"query": query, "workspace_id": workspace_id, "filters": filters}
        return self._results


@contextmanager
def _authenticated_as(membership):
    """Stands in for the SDK's own AuthContextMiddleware, which normally
    sets this contextvar from the request's validated bearer token before
    a tool function runs (see mcp_server/auth.py -- same claims shape
    LorebaseTokenVerifier.verify_token() returns for a real request).
    """
    access_token = AccessToken(
        token="test-token",
        client_id="test-client",
        scopes=[],
        claims={"workspace_id": str(membership.workspace_id)},
    )
    reset_token = auth_context_var.set(AuthenticatedUser(access_token))
    try:
        yield
    finally:
        auth_context_var.reset(reset_token)


def test_search_knowledge_scopes_to_the_callers_workspace() -> None:
    membership = MembershipFactory()
    document = DocumentFactory(source__workspace=membership.workspace)
    chunk = ChunkFactory(document=document, content="Hybrid search combines BM25 and embeddings.")
    retriever = _StubRetriever([RetrievalResult(chunk=chunk, score=0.9)])

    with (
        _authenticated_as(membership),
        patch("mcp_server.tools.get_retriever", return_value=retriever),
    ):
        results = search_knowledge(query="hybrid search")

    assert retriever.last_call["workspace_id"] == membership.workspace_id
    assert results == [
        {
            "chunk_id": str(chunk.id),
            "document_id": str(document.id),
            "document_path": document.path,
            "heading": chunk.heading_path,
            "content": chunk.content,
            "score": 0.9,
        }
    ]


def test_search_knowledge_requires_authentication() -> None:
    with pytest.raises(ValueError, match="No authenticated workspace"):
        search_knowledge(query="anything")


def test_get_document_returns_ordered_chunks() -> None:
    membership = MembershipFactory()
    document = DocumentFactory(source__workspace=membership.workspace, title="My note")
    second = ChunkFactory(document=document, index=1, content="second", heading_path="B")
    first = ChunkFactory(document=document, index=0, content="first", heading_path="A")

    with _authenticated_as(membership):
        result = get_document(document_id=str(document.id))

    assert result["title"] == "My note"
    assert result["chunks"] == [
        {"heading": first.heading_path, "content": "first"},
        {"heading": second.heading_path, "content": "second"},
    ]


def test_get_document_rejects_a_document_from_another_workspace() -> None:
    membership = MembershipFactory()
    other_document = DocumentFactory()  # different workspace

    with _authenticated_as(membership), pytest.raises(ValueError, match="No document"):
        get_document(document_id=str(other_document.id))


def test_list_sources_scopes_to_the_callers_workspace() -> None:
    membership = MembershipFactory()
    own_source = SourceFactory(workspace=membership.workspace, name="Own notes")
    DocumentFactory(source=own_source)
    SourceFactory()  # a different workspace, must not appear

    with _authenticated_as(membership):
        result = list_sources()

    assert len(result) == 1
    assert result[0]["name"] == "Own notes"
    assert result[0]["document_count"] == 1
