import logging
from typing import cast

import voyageai
from django.conf import settings

from rag.embeddings.base import EmbeddingProvider

logger = logging.getLogger(__name__)


class VoyageEmbeddingProvider(EmbeddingProvider):
    """voyage-4 by default (settings.EMBEDDING_MODEL). Retries for
    rate-limit/timeout/service-unavailable errors are handled inside the
    SDK itself (voyageai.Client(max_retries=...) already wraps calls in
    tenacity with exponential backoff+jitter) — nothing to duplicate here.
    Batching is NOT handled by the SDK, though: embed() sends the whole
    text list in one request, so a list larger than Voyage's own batch
    limit has to be split before calling it.
    """

    def __init__(self) -> None:
        self._client = voyageai.Client(api_key=settings.VOYAGE_API_KEY, max_retries=3)
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
            result = self._client.embed(
                batch,
                model=self._model,
                input_type=input_type,
                output_dimension=self._dimensions,
            )
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
                len(batch), input_type, total_tokens, cost,
            )
        else:
            logger.info(
                "Embedded %d texts (%s): %d tokens (set "
                "EMBEDDING_COST_PER_MILLION_TOKENS_USD for a cost estimate)",
                len(batch), input_type, total_tokens,
            )
