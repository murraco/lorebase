import pytest

from core.factories import WorkspaceFactory
from ingestion.factories import ChunkFactory
from rag.reranking.base import RerankerUnavailableError
from rag.reranking.factory import get_reranker
from rag.retrieval.base import RetrievalResult
from rag.retrieval.reranking import RerankingRetriever
from sources.factories import DocumentFactory

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _clear_reranker_cache(settings):
    settings.RERANK_PROVIDER = "fake"
    get_reranker.cache_clear()
    yield
    get_reranker.cache_clear()


class _StubInnerRetriever:
    """Not a real Retriever subclass — RerankingRetriever only ever calls
    .search() on whatever it wraps, so a duck-typed stub is enough here.
    """

    def __init__(self, results: list[RetrievalResult]) -> None:
        self._results = results

    def search(self, query, *, workspace_id, top_k=10, filters=None):
        return self._results[:top_k]


def test_reranking_reorders_by_actual_relevance() -> None:
    workspace = WorkspaceFactory()
    document = DocumentFactory(source__workspace=workspace)
    weak = ChunkFactory(document=document, content="mentions kubernetes only in passing")
    strong = ChunkFactory(
        document=document, content="kubernetes deployment kubernetes deployment guide"
    )
    inner = _StubInnerRetriever(
        [
            RetrievalResult(chunk=weak, score=0.9),  # ranked first by the (stub) inner retriever...
            RetrievalResult(chunk=strong, score=0.1),
        ]
    )

    results = RerankingRetriever(inner).search("kubernetes deployment", workspace_id=workspace.id)

    # ...but the reranker looks at query+content together and flips it.
    assert results[0].chunk.id == strong.id


def test_respects_top_k_after_reranking() -> None:
    workspace = WorkspaceFactory()
    document = DocumentFactory(source__workspace=workspace)
    chunks = [ChunkFactory(document=document, content=f"kubernetes chunk {i}") for i in range(5)]
    inner = _StubInnerRetriever([RetrievalResult(chunk=c, score=1.0) for c in chunks])

    results = RerankingRetriever(inner).search("kubernetes", workspace_id=workspace.id, top_k=2)

    assert len(results) == 2


def test_empty_candidates_short_circuits() -> None:
    workspace = WorkspaceFactory()
    inner = _StubInnerRetriever([])

    results = RerankingRetriever(inner).search("anything", workspace_id=workspace.id)

    assert results == []


def test_falls_back_to_unreranked_results_when_reranker_is_unavailable(monkeypatch) -> None:
    """Regression guard for a real production bug: a Voyage RateLimitError
    propagated all the way up as an unhandled 500 on the chat endpoint.
    The inner retriever's own ordering (still a real, hybrid-fused result
    set) is a reasonable degraded answer — far better than failing the
    whole request.
    """
    workspace = WorkspaceFactory()
    document = DocumentFactory(source__workspace=workspace)
    chunks = [ChunkFactory(document=document, content=f"chunk {i}") for i in range(3)]
    inner = _StubInnerRetriever([RetrievalResult(chunk=c, score=1.0) for c in chunks])

    class _FailingReranker:
        def rerank(self, query, documents, top_k):
            raise RerankerUnavailableError("rate limited")

    monkeypatch.setattr("rag.retrieval.reranking.get_reranker", lambda: _FailingReranker())

    results = RerankingRetriever(inner).search("query", workspace_id=workspace.id, top_k=2)

    assert [result.chunk.id for result in results] == [chunks[0].id, chunks[1].id]
