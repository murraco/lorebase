from django.conf import settings

from rag.reranking.base import RerankedDocument, Reranker


class LocalReranker(Reranker):
    """A cross-encoder running entirely in-process via sentence-transformers
    — no external API, so no rate limit and no per-call cost. Exists
    specifically to eliminate the class of bug the Voyage-backed reranker
    kept hitting: a free-tier account's rate limit turning into either a
    500 or, worse, silently degraded retrieval quality once the fallback
    in RerankingRetriever kicks in.

    Default model (settings.LOCAL_RERANK_MODEL) is multilingual
    (cross-encoder/mmarco-mMiniLMv2-L12-H384-v1, trained on MMARCO across
    14 languages including English and Spanish) — not the smaller
    English-only cross-encoder/ms-marco-MiniLM-L-6-v2 that's the usual
    lightweight default, since the actual notes here are a real mix of
    English and Spanish. Deliberately NOT one of the newer, larger
    multilingual rerankers (jinaai/jina-reranker-v2-base-multilingual,
    Alibaba-NLP/gte-multilingual-reranker-base): both ship custom modeling
    code that needs trust_remote_code=True, and both broke in practice —
    Jina's failed to import against the installed transformers version
    entirely. This model uses a standard architecture, no custom code, no
    version-compatibility gamble, and it's Apache-2.0 (no non-commercial
    restriction, unlike Jina's CC-BY-NC-4.0).

    The model loads lazily, on first use rather than at import time: the
    model download/load isn't something every management command or
    Celery worker boot should pay for just importing this module, and
    Django's dev-server autoreload would otherwise pay it on every single
    code change.
    """

    def __init__(self) -> None:
        self._model = None

    def _cross_encoder(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(settings.LOCAL_RERANK_MODEL)
        return self._model

    def rerank(self, query: str, documents: list[str], top_k: int) -> list[RerankedDocument]:
        if not documents:
            return []
        scores = self._cross_encoder().predict([(query, document) for document in documents])
        ranked = sorted(enumerate(scores), key=lambda pair: pair[1], reverse=True)
        return [
            RerankedDocument(index=index, score=float(score)) for index, score in ranked[:top_k]
        ]
