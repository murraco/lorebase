from uuid import UUID

from pgvector.django import CosineDistance

from ingestion.models import Chunk
from rag.embeddings.factory import get_embedding_provider
from rag.retrieval.base import RetrievalFilters, RetrievalResult, Retriever
from rag.retrieval.filtering import apply_filters


class DenseRetriever(Retriever):
    """Nearest neighbors in embedding space, via pgvector's CosineDistance
    — compiles to the `<=>` operator, using the HNSW index on
    Chunk.embedding. Catches paraphrases and semantic matches sharing no
    exact words with the query.
    """

    def search(
        self,
        query: str,
        *,
        workspace_id: UUID,
        top_k: int = 10,
        filters: RetrievalFilters | None = None,
    ) -> list[RetrievalResult]:
        query_vector = get_embedding_provider().embed_query(query)

        qs = Chunk.objects.filter(
            document__source__workspace_id=workspace_id, embedding__isnull=False
        )
        qs = apply_filters(qs, filters)
        qs = qs.annotate(distance=CosineDistance("embedding", query_vector)).order_by("distance")
        qs = qs[:top_k]
        # Cosine distance: 0 = identical, 2 = opposite. Flipped to a
        # similarity score so higher-is-better matches the lexical side.
        return [RetrievalResult(chunk=chunk, score=1 - chunk.distance) for chunk in qs]
