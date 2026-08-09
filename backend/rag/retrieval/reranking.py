import logging
from uuid import UUID

from rag.reranking.base import RerankerUnavailableError
from rag.reranking.factory import get_reranker
from rag.retrieval.base import RetrievalFilters, RetrievalResult, Retriever
from rag.retrieval.tracing import traced_search

logger = logging.getLogger(__name__)


class RerankingRetriever(Retriever):
    """Wraps any other Retriever and reranks its output — a decorator,
    not a subclass of whatever it wraps. Works over HybridRetriever in
    production, but the same wrapper works over LexicalRetriever or
    DenseRetriever alone too, e.g. for isolating what reranking alone
    contributes in an evaluation run.
    """

    def __init__(self, inner: Retriever, fetch_k: int = 50) -> None:
        self._inner = inner
        self._fetch_k = fetch_k

    @traced_search
    def search(
        self,
        query: str,
        *,
        workspace_id: UUID,
        top_k: int = 10,
        filters: RetrievalFilters | None = None,
    ) -> list[RetrievalResult]:
        candidates = self._inner.search(
            query, workspace_id=workspace_id, top_k=self._fetch_k, filters=filters
        )
        if not candidates:
            return []

        # A reranker outage shouldn't fail the whole chat turn — the inner
        # retriever's own ordering (lexical/dense RRF fusion) is still a
        # reasonable answer, just not cross-encoder-refined. Silently
        # degraded quality beats a 500.
        try:
            reranked = get_reranker().rerank(
                query, [candidate.chunk.content for candidate in candidates], top_k=top_k
            )
        except RerankerUnavailableError:
            logger.warning(
                "Reranker unavailable, falling back to unreranked results", exc_info=True
            )
            return candidates[:top_k]

        return [
            RetrievalResult(chunk=candidates[item.index].chunk, score=item.score)
            for item in reranked
        ]
