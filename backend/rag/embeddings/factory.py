from functools import lru_cache

from django.conf import settings

from rag.embeddings.base import EmbeddingProvider


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    """Which provider is a settings choice (EMBEDDING_PROVIDER), not
    something any call site decides — swapping providers is a one-line
    settings change, never a code change. Memoized: constructing a
    VoyageEmbeddingProvider builds an HTTP client, no need to redo that on
    every call.
    """
    if settings.EMBEDDING_PROVIDER == "voyage":
        from rag.embeddings.voyage import VoyageEmbeddingProvider

        return VoyageEmbeddingProvider()
    if settings.EMBEDDING_PROVIDER == "local":
        from rag.embeddings.local import LocalEmbeddingProvider

        return LocalEmbeddingProvider()
    if settings.EMBEDDING_PROVIDER == "fake":
        from rag.embeddings.fake import FakeEmbeddingProvider

        return FakeEmbeddingProvider(dimensions=settings.EMBEDDING_DIMENSIONS)
    raise ValueError(f"Unknown EMBEDDING_PROVIDER: {settings.EMBEDDING_PROVIDER!r}")
