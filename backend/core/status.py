"""Effective runtime configuration, resolved rather than echoed.

The point of this is catching misconfiguration, so it deliberately
reports which model is *actually in use* for the active provider instead
of dumping every setting: EMBEDDING_MODEL and LOCAL_EMBEDDING_MODEL are
both always set, and only one of them means anything at a given moment.
Showing both is how a wrong provider stays invisible — which is exactly
how EMBEDDING_PROVIDER=fake once ran against real data unnoticed.
"""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from django.conf import settings
from django.db.models import Count, Q

from ingestion.models import Chunk
from sources.models import Document, Source


@dataclass
class ProviderStatus:
    provider: str
    model: str


@dataclass
class SystemStatus:
    embedding: ProviderStatus
    reranking: ProviderStatus
    llm: ProviderStatus
    embedding_dimensions: int
    retrieval_strategy: str
    sources: int
    documents: int
    chunks: int
    embedded_chunks: int
    # True when a provider that produces meaningless output is active, so
    # the UI can call it out rather than showing it as just another value.
    using_fake_providers: bool


def _embedding_status() -> ProviderStatus:
    provider = settings.EMBEDDING_PROVIDER
    if provider == "local":
        return ProviderStatus(provider, settings.LOCAL_EMBEDDING_MODEL)
    if provider == "voyage":
        return ProviderStatus(provider, settings.EMBEDDING_MODEL)
    return ProviderStatus(provider, "-")


def _reranking_status() -> ProviderStatus:
    provider = settings.RERANK_PROVIDER
    if provider == "local":
        return ProviderStatus(provider, settings.LOCAL_RERANK_MODEL)
    if provider == "voyage":
        return ProviderStatus(provider, settings.RERANK_MODEL)
    return ProviderStatus(provider, "-")


def _llm_status() -> ProviderStatus:
    provider = settings.LLM_PROVIDER
    if provider == "anthropic":
        return ProviderStatus(provider, settings.LLM_MODEL)
    return ProviderStatus(provider, "-")


def get_system_status(workspace_ids: list[UUID]) -> SystemStatus:
    """Counts are scoped to the caller's workspaces — this is a status
    panel for your own data, not a server-wide admin view.
    """
    chunk_counts: dict[str, Any] = Chunk.objects.filter(
        document__source__workspace_id__in=workspace_ids
    ).aggregate(
        total=Count("id"),
        embedded=Count("id", filter=Q(embedding__isnull=False)),
    )

    embedding = _embedding_status()
    reranking = _reranking_status()
    llm = _llm_status()

    return SystemStatus(
        embedding=embedding,
        reranking=reranking,
        llm=llm,
        embedding_dimensions=settings.EMBEDDING_DIMENSIONS,
        retrieval_strategy=settings.RETRIEVAL_STRATEGY,
        sources=Source.objects.filter(workspace_id__in=workspace_ids).count(),
        documents=Document.objects.filter(
            source__workspace_id__in=workspace_ids, deleted=False
        ).count(),
        chunks=chunk_counts["total"] or 0,
        embedded_chunks=chunk_counts["embedded"] or 0,
        using_fake_providers="fake" in {embedding.provider, reranking.provider, llm.provider},
    )
