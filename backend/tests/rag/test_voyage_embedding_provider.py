from unittest.mock import MagicMock, patch

import pytest
import voyageai

from rag.embeddings.base import EmbeddingProviderUnavailableError
from rag.embeddings.voyage import VoyageEmbeddingProvider


@pytest.fixture
def mock_client():
    with patch("rag.embeddings.voyage.voyageai.Client") as mock_client_cls:
        yield mock_client_cls.return_value


def test_translates_rate_limit_error_into_embedding_provider_unavailable(
    settings, mock_client
) -> None:
    """The bug hit live running the real embedding backfill: a
    RateLimitError propagated uncaught out of embed_documents(), killing
    the whole Celery task after embedding zero chunks.
    """
    settings.VOYAGE_API_KEY = "test-key"
    mock_client.embed.side_effect = voyageai.error.RateLimitError("reduced rate limits")

    with pytest.raises(EmbeddingProviderUnavailableError):
        VoyageEmbeddingProvider().embed_documents(["doc"])


def test_translates_service_unavailable_error(settings, mock_client) -> None:
    settings.VOYAGE_API_KEY = "test-key"
    mock_client.embed.side_effect = voyageai.error.ServiceUnavailableError("down")

    with pytest.raises(EmbeddingProviderUnavailableError):
        VoyageEmbeddingProvider().embed_query("query")


def test_does_not_swallow_unrelated_errors(settings, mock_client) -> None:
    settings.VOYAGE_API_KEY = "test-key"
    mock_client.embed.side_effect = voyageai.error.InvalidRequestError("bad request")

    with pytest.raises(voyageai.error.InvalidRequestError):
        VoyageEmbeddingProvider().embed_documents(["doc"])


def test_returns_vectors_on_success(settings, mock_client) -> None:
    settings.VOYAGE_API_KEY = "test-key"
    settings.EMBEDDING_DIMENSIONS = 3
    mock_client.embed.return_value = MagicMock(embeddings=[[0.1, 0.2, 0.3]], total_tokens=5)

    result = VoyageEmbeddingProvider().embed_documents(["doc"])

    assert result == [[0.1, 0.2, 0.3]]
