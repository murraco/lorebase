from collections import defaultdict
from uuid import UUID

from ingestion.models import Chunk
from rag.retrieval.base import RetrievalFilters, RetrievalResult, Retriever
from rag.retrieval.dense import DenseRetriever
from rag.retrieval.lexical import LexicalRetriever
from rag.retrieval.tracing import traced_search

# The constant from the original paper, now a de facto industry default.
RRF_K = 60


class HybridRetriever(Retriever):
    """Combines lexical and dense rankings with Reciprocal Rank Fusion:
    score(chunk) = sum(1 / (RRF_K + rank_in_list)) across every list it
    appears in. Deliberately ignores the two retrievers' raw scores (a
    ts_rank_cd value and a cosine similarity live on incomparable scales)
    and uses only rank position — Cormack, Clarke & Grossman, "Reciprocal
    Rank Fusion outperforms Condorcet and Individual Rank Learning
    Methods" (SIGIR 2009).
    """

    def __init__(self, fetch_k: int = 50) -> None:
        self._lexical = LexicalRetriever()
        self._dense = DenseRetriever()
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
        lexical_results = self._lexical.search(
            query, workspace_id=workspace_id, top_k=self._fetch_k, filters=filters
        )
        dense_results = self._dense.search(
            query, workspace_id=workspace_id, top_k=self._fetch_k, filters=filters
        )

        scores: dict[UUID, float] = defaultdict(float)
        chunks_by_id: dict[UUID, Chunk] = {}
        for results in (lexical_results, dense_results):
            for rank, result in enumerate(results, start=1):
                scores[result.chunk.id] += 1 / (RRF_K + rank)
                chunks_by_id[result.chunk.id] = result.chunk

        ranked_ids = sorted(scores, key=lambda chunk_id: scores[chunk_id], reverse=True)
        return [
            RetrievalResult(chunk=chunks_by_id[chunk_id], score=scores[chunk_id])
            for chunk_id in ranked_ids[:top_k]
        ]
