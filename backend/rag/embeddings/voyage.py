import logging
from typing import cast

import voyageai
from django.conf import settings

from rag.embeddings.base import EmbeddingProvider, EmbeddingProviderUnavailableError

logger = logging.getLogger(__name__)


class VoyageEmbeddingProvider(EmbeddingProvider):
    """voyage-4 by default (settings.EMBEDDING_MODEL).

    max_retries=1 (i.e. no SDK-level retry at all) — deliberately more
    aggressive than VoyageReranker's max_retries=2. Here, the SDK retrying
    on its own actively fights the task-level retry in
    rag.tasks.backfill_embeddings_task: every SDK-level attempt is a real
    request against the same 3-RPM budget, so if the SDK burns 2 requests
    before giving up, each Celery-level retry now costs double — found
    live, running the real backfill, where this compounding meant it
    never got a clean enough window to succeed at all across nearly a
    dozen Celery retries. With max_retries=1, each Celery retry costs
    exactly one real request, and the task-level backoff (which can wait
    a genuine number of seconds, unlike the SDK's few-second window) is
    what actually gets a chance to outlast the per-minute limit.

    Batching is NOT handled by the SDK: embed() sends the whole text list
    in one request, so a list larger than Voyage's own batch limit has to
    be split before calling it.
    """

    def __init__(self) -> None:
        self._client = voyageai.Client(api_key=settings.VOYAGE_API_KEY, max_retries=1)
        self._model = settings.EMBEDDING_MODEL
        self._dimensions = settings.EMBEDDING_DIMENSIONS

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts, input_type="document")

    def embed_query(self, text: str) -> list[float]:
        (vector,) = self._embed([text], input_type="query")
        return vector

    def _embed(self, texts: list[str], input_type: str) -> list[list[float]]:
        vectors: list[list[float]] = []
        batch_size = voyageai.VOYAGE_EMBED_BATCH_SIZE
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            try:
                result = self._client.embed(
                    batch,
                    model=self._model,
                    input_type=input_type,
                    output_dimension=self._dimensions,
                )
            except (
                voyageai.error.RateLimitError,
                voyageai.error.ServiceUnavailableError,
                voyageai.error.Timeout,
            ) as exc:
                raise EmbeddingProviderUnavailableError(str(exc)) from exc
            # embeddings is typed as float-or-int because Voyage also
            # supports quantized dtypes (int8/uint8/binary) via
            # output_dtype — we never pass that, so this is always floats.
            vectors.extend(cast(list[list[float]], result.embeddings))
            self._log_usage(batch, input_type, result.total_tokens)
        return vectors

    @staticmethod
    def _log_usage(batch: list[str], input_type: str, total_tokens: int) -> None:
        cost_per_million = settings.EMBEDDING_COST_PER_MILLION_TOKENS_USD
        if cost_per_million:
            cost = total_tokens / 1_000_000 * cost_per_million
            logger.info(
                "Embedded %d texts (%s): %d tokens, ~$%.5f",
                len(batch),
                input_type,
                total_tokens,
                cost,
            )
        else:
            logger.info(
                "Embedded %d texts (%s): %d tokens (set "
                "EMBEDDING_COST_PER_MILLION_TOKENS_USD for a cost estimate)",
                len(batch),
                input_type,
                total_tokens,
            )
