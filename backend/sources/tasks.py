import logging

from celery import shared_task

from rag.tasks import backfill_embeddings_task
from sources.locking import sync_lock
from sources.models import Source
from sources.sync import sync_source_with_tracking

logger = logging.getLogger(__name__)


@shared_task(
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def sync_source_task(source_id: str) -> dict[str, int | bool]:
    with sync_lock(source_id) as acquired:
        if not acquired:
            logger.info("Sync already in progress for source %s, skipping", source_id)
            return {"skipped": True}

        source = Source.objects.get(pk=source_id)
        run = sync_source_with_tracking(source)

    # Fired after releasing the sync lock (that lock is only about not
    # double-syncing this Source) and as a separate task rather than
    # inline, so a slow/rate-limited embedding run never blocks the sync
    # from reporting done, and can be retried independently of it.
    backfill_embeddings_task.delay()

    return {"added": run.added, "updated": run.updated, "deleted": run.deleted}
