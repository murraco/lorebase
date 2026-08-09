from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID

from django.core.cache import cache

LOCK_TIMEOUT_SECONDS = 60 * 30  # generous ceiling in case a sync hangs


def _lock_key(source_id: UUID | str) -> str:
    return f"sync-lock:{source_id}"


@contextmanager
def sync_lock(source_id: UUID | str) -> Iterator[bool]:
    """Yields True if the lock was acquired (caller should proceed) or False
    if another sync is already running for this source (caller should
    skip). Always released on the way out, but only by whoever acquired it.
    """
    key = _lock_key(source_id)
    acquired = cache.add(key, "1", timeout=LOCK_TIMEOUT_SECONDS)
    try:
        yield acquired
    finally:
        if acquired:
            cache.delete(key)


def _cancel_key(source_id: UUID | str) -> str:
    return f"sync-cancel:{source_id}"


# Cooperative, not a kill signal: a Celery worker can't be told to abort
# mid-iteration safely (a sync interrupted between "chunks written" and
# "embeddings queued" would leave a document half-indexed). Instead this
# flags intent, and sync_source() checks it once per document — between
# documents is always a safe, consistent point to stop, and whatever was
# ingested before the flag was seen simply stays, since sync is already
# incremental by content_hash.
def request_cancel(source_id: UUID | str) -> None:
    cache.set(_cancel_key(source_id), "1", timeout=LOCK_TIMEOUT_SECONDS)


def is_cancel_requested(source_id: UUID | str) -> bool:
    return cache.get(_cancel_key(source_id)) is not None


def clear_cancel(source_id: UUID | str) -> None:
    cache.delete(_cancel_key(source_id))
