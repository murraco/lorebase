import pytest

from core.factories import WorkspaceFactory
from ingestion.factories import ChunkFactory
from rag.retrieval.base import RetrievalFilters
from rag.retrieval.lexical import LexicalRetriever
from sources.factories import DocumentFactory, SourceFactory

pytestmark = pytest.mark.django_db


def test_finds_exact_term_match() -> None:
    workspace = WorkspaceFactory()
    document = DocumentFactory(source__workspace=workspace)
    content = "Hybrid search combines BM25 and dense retrieval."
    chunk = ChunkFactory(document=document, content=content)
    ChunkFactory(document=document, content="Something entirely unrelated about gardening.")

    results = LexicalRetriever().search("BM25", workspace_id=workspace.id)

    assert [r.chunk.id for r in results] == [chunk.id]


def test_no_match_returns_empty() -> None:
    workspace = WorkspaceFactory()
    document = DocumentFactory(source__workspace=workspace)
    ChunkFactory(document=document, content="Something about gardening.")

    results = LexicalRetriever().search("PostgreSQL", workspace_id=workspace.id)

    assert results == []


def test_does_not_cross_workspace_boundaries() -> None:
    workspace_a = WorkspaceFactory()
    workspace_b = WorkspaceFactory()
    document_b = DocumentFactory(source__workspace=workspace_b)
    ChunkFactory(document=document_b, content="Secret notes about BM25 tuning.")

    results = LexicalRetriever().search("BM25", workspace_id=workspace_a.id)

    assert results == []


def test_filters_by_source_id() -> None:
    workspace = WorkspaceFactory()
    source_a = SourceFactory(workspace=workspace)
    source_b = SourceFactory(workspace=workspace)
    chunk_a = ChunkFactory(document__source=source_a, content="BM25 details in source A.")
    ChunkFactory(document__source=source_b, content="BM25 details in source B.")

    results = LexicalRetriever().search(
        "BM25", workspace_id=workspace.id, filters=RetrievalFilters(source_ids=[source_a.id])
    )

    assert [r.chunk.id for r in results] == [chunk_a.id]


def test_ranks_better_matches_first() -> None:
    workspace = WorkspaceFactory()
    document = DocumentFactory(source__workspace=workspace)
    weak = ChunkFactory(document=document, content="This mentions retrieval only once, in passing.")
    strong = ChunkFactory(
        document=document,
        content="Retrieval retrieval retrieval: a chunk entirely about retrieval systems.",
    )

    results = LexicalRetriever().search("retrieval", workspace_id=workspace.id)

    assert [r.chunk.id for r in results] == [strong.id, weak.id]
