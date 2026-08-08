import voyageai
from django.conf import settings

from rag.reranking.base import RerankedDocument, Reranker, RerankerUnavailableError


class VoyageReranker(Reranker):
    """rerank-2.5 by default (settings.RERANK_MODEL). Same SDK client
    pattern as VoyageEmbeddingProvider — retries are handled internally.

    max_retries=2, down from the SDK's usual default: retrying helps a
    genuine transient blip (Timeout, ServiceUnavailableError), but a free
    Voyage account's rate limit (3 RPM, no payment method on file) resets
    on a per-minute window that no bounded exponential backoff is going to
    outlast. Retrying that case is close to pure wasted latency on a
    request a user is actively waiting on — better to fail fast into the
    fallback in RerankingRetriever than sit through backoff first.
    """

    def __init__(self) -> None:
        self._client = voyageai.Client(api_key=settings.VOYAGE_API_KEY, max_retries=2)
        self._model = settings.RERANK_MODEL

    def rerank(self, query: str, documents: list[str], top_k: int) -> list[RerankedDocument]:
        if not documents:
            return []
        try:
            result = self._client.rerank(query, documents, model=self._model, top_k=top_k)
        except (
            voyageai.error.RateLimitError,
            voyageai.error.ServiceUnavailableError,
            voyageai.error.Timeout,
        ) as exc:
            raise RerankerUnavailableError(str(exc)) from exc
        return [
            RerankedDocument(index=item.index, score=item.relevance_score)
            for item in result.results
        ]
