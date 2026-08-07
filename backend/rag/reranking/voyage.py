import voyageai
from django.conf import settings

from rag.reranking.base import RerankedDocument, Reranker


class VoyageReranker(Reranker):
    """rerank-2.5 by default (settings.RERANK_MODEL). Same SDK client
    pattern as VoyageEmbeddingProvider — retries are handled internally.
    """

    def __init__(self) -> None:
        self._client = voyageai.Client(api_key=settings.VOYAGE_API_KEY, max_retries=3)
        self._model = settings.RERANK_MODEL

    def rerank(self, query: str, documents: list[str], top_k: int) -> list[RerankedDocument]:
        if not documents:
            return []
        result = self._client.rerank(query, documents, model=self._model, top_k=top_k)
        return [
            RerankedDocument(index=item.index, score=item.relevance_score)
            for item in result.results
        ]
