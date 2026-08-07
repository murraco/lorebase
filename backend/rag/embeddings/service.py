import logging

from ingestion.models import Chunk
from rag.embeddings.factory import get_embedding_provider

logger = logging.getLogger(__name__)


def embed_pending_chunks(batch_size: int = 100) -> int:
    """Finds every Chunk with embedding=NULL (freshly ingested, or left
    over from a provider switch) and embeds it, in DB-query batches of
    `batch_size`. Independent of the provider's own API batch size — the
    provider handles that internally.
    """
    provider = get_embedding_provider()
    total = 0

    while True:
        chunks = list(Chunk.objects.filter(embedding__isnull=True)[:batch_size])
        if not chunks:
            break

        vectors = provider.embed_documents([chunk.content for chunk in chunks])
        for chunk, vector in zip(chunks, vectors, strict=True):
            chunk.embedding = vector
        Chunk.objects.bulk_update(chunks, ["embedding"])

        total += len(chunks)
        logger.info("Embedded %d chunks (%d total this run)", len(chunks), total)

    return total
