import pytest

from ingestion.pipeline import process_document
from rag.embeddings.base import EmbeddingProviderUnavailableError
from rag.tasks import backfill_embeddings_task
from sources.factories import DocumentFactory

pytestmark = pytest.mark.django_db


def test_task_embeds_pending_chunks_end_to_end() -> None:
    document = DocumentFactory()
    process_document(document, text="# A\n\nsome text")

    result = backfill_embeddings_task.delay().get()

    assert result == {"embedded": 1}
    assert not document.chunks.filter(embedding__isnull=True).exists()


def test_task_retries_on_embedding_provider_unavailable() -> None:
    """Regression guard for a real bug hit live: an uncaught RateLimitError
    from Voyage killed the whole backfill after embedding zero chunks,
    with nothing retrying on its own. The task is resumable by
    construction (embed_pending_chunks() always queries for whatever
    still has embedding=NULL), so retrying the whole task is safe and
    correct — this only asserts the retry is actually configured, since
    CELERY_TASK_ALWAYS_EAGER in tests doesn't exercise Celery's retry
    machinery the way a real worker would.
    """
    assert backfill_embeddings_task.autoretry_for == (EmbeddingProviderUnavailableError,)
    assert backfill_embeddings_task.retry_backoff is True
    assert backfill_embeddings_task.retry_backoff_max == 60
