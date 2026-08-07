from rag.reranking.base import RerankedDocument, Reranker


class FakeReranker(Reranker):
    """Deterministic word-overlap scoring, no network calls. Good enough
    to exercise the reranking *plumbing* in tests (does the wrapping,
    indexing, and top_k truncation work) — not a stand-in for real
    semantic reranking quality.
    """

    def rerank(self, query: str, documents: list[str], top_k: int) -> list[RerankedDocument]:
        query_words = set(query.lower().split())
        scored = [
            RerankedDocument(index=i, score=len(query_words & set(doc.lower().split())))
            for i, doc in enumerate(documents)
        ]
        scored.sort(key=lambda d: d.score, reverse=True)
        return scored[:top_k]
