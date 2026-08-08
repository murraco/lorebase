from celery import shared_task

from rag.embeddings.base import EmbeddingProviderUnavailableError
from rag.embeddings.service import embed_pending_chunks


@shared_task(
    autoretry_for=(EmbeddingProviderUnavailableError,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_kwargs={"max_retries": 30},
)
def backfill_embeddings_task(batch_size: int = 100) -> dict[str, int]:
    """Resumable by construction: embed_pending_chunks() always queries
    for whatever still has embedding=NULL, so retrying the whole task
    after a rate limit picks up exactly where the last attempt left off
    — no double-embedding, no lost progress from DB-batches that already
    succeeded before the one that failed.

    A real rate limit was hit live running this exact backfill: the
    first DB-batch failed with an uncaught RateLimitError, and with no
    retry configured, that silently killed the task after embedding zero
    chunks — the other ~14 batches never even got attempted. 30 retries
    with a 60s backoff cap gives this up to half an hour to work through
    a free-tier 3 RPM ceiling, one DB-batch (one API call) at a time.
    """
    return {"embedded": embed_pending_chunks(batch_size=batch_size)}
