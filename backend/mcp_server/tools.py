from datetime import datetime
from typing import Any
from uuid import UUID

from mcp.server.auth.middleware.auth_context import get_access_token

from mcp_server.server import mcp
from rag.retrieval.base import RetrievalFilters
from rag.retrieval.factory import get_retriever
from sources.models import Document, Source


def _current_workspace_id() -> UUID:
    """Every tool call is scoped to the caller's workspace this way --
    same idea as DocumentViewSet.get_queryset() in the DRF API, just read
    from the AccessToken our own LorebaseTokenVerifier built (see
    mcp_server/auth.py) instead of a Django session. get_access_token()
    reads from a contextvar the SDK's auth middleware sets before this
    tool function runs, so there's no need to pass it in explicitly.
    """
    access_token = get_access_token()
    claims = access_token.claims if access_token else None
    if claims is None or "workspace_id" not in claims:
        raise ValueError("No authenticated workspace for this request.")
    return UUID(claims["workspace_id"])


@mcp.tool()
def search_knowledge(
    query: str,
    source_ids: list[str] | None = None,
    updated_after: str | None = None,
) -> list[dict[str, Any]]:
    """Search the user's notes for chunks relevant to a query. Optionally
    restrict to specific sources (by id) or notes updated after a given
    ISO date.
    """
    filters = RetrievalFilters(
        source_ids=[UUID(source_id) for source_id in source_ids] if source_ids else None,
        updated_after=datetime.fromisoformat(updated_after) if updated_after else None,
    )
    results = get_retriever().search(
        query, workspace_id=_current_workspace_id(), top_k=5, filters=filters
    )
    return [
        {
            "chunk_id": str(result.chunk.id),
            "document_id": str(result.chunk.document_id),
            "document_path": result.chunk.document.path,
            "heading": result.chunk.heading_path,
            "content": result.chunk.content,
            "score": result.score,
        }
        for result in results
    ]


@mcp.tool()
def get_document(document_id: str) -> dict[str, Any]:
    """Fetch a document by id -- its metadata and full indexed content, as
    an ordered list of chunks, each with the heading it falls under.
    """
    try:
        document = Document.objects.select_related("source").get(
            id=document_id, source__workspace_id=_current_workspace_id(), deleted=False
        )
    except Document.DoesNotExist as exc:
        raise ValueError(f"No document with id {document_id} in this workspace.") from exc

    return {
        "id": str(document.id),
        "title": document.title,
        "path": document.path,
        "source": document.source.name,
        "chunks": [
            {"heading": chunk.heading_path, "content": chunk.content}
            for chunk in document.chunks.order_by("index")
        ],
    }


@mcp.tool()
def list_sources() -> list[dict[str, Any]]:
    """List the knowledge sources configured in the user's workspace."""
    sources = Source.objects.filter(workspace_id=_current_workspace_id())
    return [
        {
            "id": str(source.id),
            "name": source.name,
            "type": source.type,
            "status": source.status,
            "document_count": source.documents.filter(deleted=False).count(),
        }
        for source in sources
    ]
