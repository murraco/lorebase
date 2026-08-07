from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from ingestion.models import Chunk


@dataclass
class RetrievalFilters:
    source_ids: list[UUID] | None = None
    updated_after: datetime | None = None


@dataclass
class RetrievalResult:
    chunk: Chunk
    score: float


class Retriever(ABC):
    """One interface for lexical, dense, hybrid, and reranked retrieval —
    interchangeable via settings.RETRIEVAL_STRATEGY (see
    rag/retrieval/factory.py). workspace_id is required, not optional: a
    retriever that could silently search across workspaces is a
    multi-tenancy bug waiting to happen.
    """

    @abstractmethod
    def search(
        self,
        query: str,
        *,
        workspace_id: UUID,
        top_k: int = 10,
        filters: RetrievalFilters | None = None,
    ) -> list[RetrievalResult]: ...
