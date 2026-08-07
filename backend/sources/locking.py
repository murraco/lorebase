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
