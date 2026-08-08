import pytest

from core.factories import WorkspaceFactory
from ingestion.factories import ChunkFactory
from rag.retrieval.base import RetrievalResult
from rag.retrieval.date_matching import DateAwareRetriever
from sources.factories import DocumentFactory

pytestmark = pytest.mark.django_db


class _StubInnerRetriever:
    """Not a real Retriever subclass — DateAwareRetriever only ever calls
    .search() on whatever it wraps, so a duck-typed stub is enough here.
    """

    def __init__(self, results: list[RetrievalResult]) -> None:
        self._results = results

    def search(self, query, *, workspace_id, top_k=10, filters=None):
        return self._results[:top_k]


def test_forces_in_a_chunk_matching_an_iso_date_the_inner_retriever_missed() -> None:
    """Regression guard for a real bug hit live: neither lexical nor dense
    search reliably surfaced a specific day's journal entry (lexical's
    AND-of-every-term semantics fails when the query has words the
    content doesn't share; dense embeddings alone don't differentiate
    well between similarly-shaped daily entries).
    """
    workspace = WorkspaceFactory()
    document = DocumentFactory(source__workspace=workspace)
    dated_chunk = ChunkFactory(
        document=document, heading_path="2025-07-21", content="2025-07-21\n\nDid some work."
    )
    unrelated_chunk = ChunkFactory(document=document, content="unrelated content")
    inner = _StubInnerRetriever([RetrievalResult(chunk=unrelated_chunk, score=0.5)])

    results = DateAwareRetriever(inner).search(
        "What did I do on 2025-07-21?", workspace_id=workspace.id
    )

    assert dated_chunk.id in {result.chunk.id for result in results}


def test_does_not_duplicate_a_chunk_the_inner_retriever_already_found() -> None:
    workspace = WorkspaceFactory()
    document = DocumentFactory(source__workspace=workspace)
    dated_chunk = ChunkFactory(document=document, content="2025-07-21\n\nDid some work.")
    inner = _StubInnerRetriever([RetrievalResult(chunk=dated_chunk, score=0.9)])

    results = DateAwareRetriever(inner).search(
        "What did I do on 2025-07-21?", workspace_id=workspace.id
    )

    ids = [result.chunk.id for result in results]
    assert ids.count(dated_chunk.id) == 1


def test_no_date_in_query_leaves_inner_results_untouched() -> None:
    workspace = WorkspaceFactory()
    document = DocumentFactory(source__workspace=workspace)
    chunk = ChunkFactory(document=document, content="no date here")
    inner = _StubInnerRetriever([RetrievalResult(chunk=chunk, score=0.5)])

    results = DateAwareRetriever(inner).search("what is hybrid search?", workspace_id=workspace.id)

    assert [result.chunk.id for result in results] == [chunk.id]


def test_date_matches_are_prioritized_and_top_k_is_still_respected() -> None:
    workspace = WorkspaceFactory()
    document = DocumentFactory(source__workspace=workspace)
    dated_chunk = ChunkFactory(document=document, content="2025-07-21\n\nentry")
    inner_chunks = [ChunkFactory(document=document, content=f"inner {i}") for i in range(5)]
    inner = _StubInnerRetriever([RetrievalResult(chunk=c, score=1.0) for c in inner_chunks])

    results = DateAwareRetriever(inner).search("2025-07-21", workspace_id=workspace.id, top_k=3)

    assert len(results) == 3
    assert results[0].chunk.id == dated_chunk.id


def test_only_matches_chunks_in_the_given_workspace() -> None:
    workspace = WorkspaceFactory()
    other_document = DocumentFactory()  # different workspace
    ChunkFactory(document=other_document, content="2025-07-21\n\nsomeone else's entry")
    inner = _StubInnerRetriever([])

    results = DateAwareRetriever(inner).search("2025-07-21", workspace_id=workspace.id)

    assert results == []
