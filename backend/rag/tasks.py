from celery import shared_task

from rag.embeddings.service import embed_pending_chunks


@shared_task
def backfill_embeddings_task(batch_size: int = 100) -> dict[str, int]:
    return {"embedded": embed_pending_chunks(batch_size=batch_size)}
