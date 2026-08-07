from unittest.mock import patch

import pytest
from django.conf import settings

from core.factories import WorkspaceFactory
from ingestion.factories import ChunkFactory
from rag.retrieval.base import RetrievalFilters
from rag.retrieval.dense import DenseRetriever
from sources.factories import DocumentFactory, SourceFactory

pytestmark = pytest.mark.django_db


def _unit_vector(index: int = 0) -> list[float]:
    """A basis vector: all zeros except a 1 at `index`. Easy to reason
    about exactly — identical vectors have cosine distance 0, opposite
    (negated) vectors have distance 2 — without needing a real embedding
    model's semantics, which is exactly the point: this tests our
    nearest-neighbor SQL, not whether Voyage's model is good.
    """
    vector = [0.0] * settings.EMBEDDING_DIMENSIONS
    vector[index] = 1.0
    return vector


def _search_with_query_vector(query_vector: list[float], **kwargs):
    with patch("rag.retrieval.dense.get_embedding_provider") as mock_factory:
        mock_factory.return_value.embed_query.return_value = query_vector
        return DenseRetriever().search("irrelevant text", **kwargs)


def test_finds_nearest_neighbor_first() -> None:
    workspace = WorkspaceFactory()
    document = DocumentFactory(source__workspace=workspace)
    query_vector = _unit_vector()
    close = ChunkFactory(document=document, embedding=query_vector)
    far = ChunkFactory(document=document, embedding=[-v for v in query_vector])

    results = _search_with_query_vector(query_vector, workspace_id=workspace.id)

    assert [r.chunk.id for r in results] == [close.id, far.id]


def test_excludes_chunks_without_an_embedding() -> None:
    workspace = WorkspaceFactory()
    document = DocumentFactory(source__workspace=workspace)
    query_vector = _unit_vector()
    embedded = ChunkFactory(document=document, embedding=query_vector)
    ChunkFactory(document=document, embedding=None)

    results = _search_with_query_vector(query_vector, workspace_id=workspace.id)

    assert [r.chunk.id for r in results] == [embedded.id]


def test_does_not_cross_workspace_boundaries() -> None:
    workspace_a = WorkspaceFactory()
    workspace_b = WorkspaceFactory()
    query_vector = _unit_vector()
    document_b = DocumentFactory(source__workspace=workspace_b)
    ChunkFactory(document=document_b, embedding=query_vector)

    results = _search_with_query_vector(query_vector, workspace_id=workspace_a.id)

    assert results == []


def test_filters_by_source_id() -> None:
    workspace = WorkspaceFactory()
    source_a = SourceFactory(workspace=workspace)
    source_b = SourceFactory(workspace=workspace)
    query_vector = _unit_vector()
    chunk_a = ChunkFactory(document__source=source_a, embedding=query_vector)
    ChunkFactory(document__source=source_b, embedding=query_vector)

    results = _search_with_query_vector(
        query_vector, workspace_id=workspace.id, filters=RetrievalFilters(source_ids=[source_a.id])
    )

    assert [r.chunk.id for r in results] == [chunk_a.id]
