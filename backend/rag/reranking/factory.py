from functools import lru_cache

from django.conf import settings

from rag.reranking.base import Reranker


@lru_cache
def get_reranker() -> Reranker:
    if settings.RERANK_PROVIDER == "voyage":
        from rag.reranking.voyage import VoyageReranker

        return VoyageReranker()
    if settings.RERANK_PROVIDER == "fake":
        from rag.reranking.fake import FakeReranker

        return FakeReranker()
    raise ValueError(f"Unknown RERANK_PROVIDER: {settings.RERANK_PROVIDER!r}")
