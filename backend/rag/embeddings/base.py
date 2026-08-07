from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    """Text -> vector, behind an interface so the provider is a settings
    choice, not something wired into call sites. `embed_documents` and
    `embed_query` are separate on purpose: modern embedding APIs are
    asymmetric — a query and the document that answers it are embedded
    with a different mode, because the two roles aren't textually similar
    even when they're semantically related.
    """

    @property
    @abstractmethod
    def dimensions(self) -> int: ...

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts in "document" mode."""

    @abstractmethod
    def embed_query(self, text: str) -> list[float]:
        """Embed a single text in "query" mode."""
