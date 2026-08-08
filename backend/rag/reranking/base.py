from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class RerankedDocument:
    index: int  # position in the `documents` list that was passed in
    score: float


class RerankerUnavailableError(Exception):
    """The reranker's backing service is down, rate-limited, or timed out
    — as opposed to a bug in how we're calling it. Provider implementations
    translate their own SDK's transient-failure exceptions into this one,
    so callers (RerankingRetriever) can catch a single, provider-agnostic
    type and fall back to unreranked results instead of failing the whole
    request.
    """


class Reranker(ABC):
    """A cross-encoder: scores query+document together in one pass,
    instead of comparing independently-computed vectors like embeddings
    do. Much more accurate, much more expensive — only ever run over a
    small top-N candidate set a cheaper retriever already narrowed down,
    never over a whole corpus.
    """

    @abstractmethod
    def rerank(self, query: str, documents: list[str], top_k: int) -> list[RerankedDocument]: ...
