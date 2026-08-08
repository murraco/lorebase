from unittest.mock import MagicMock, patch

import pytest
import voyageai

from rag.reranking.base import RerankerUnavailableError
from rag.reranking.voyage import VoyageReranker


@pytest.fixture
def mock_client():
    with patch("rag.reranking.voyage.voyageai.Client") as mock_client_cls:
        yield mock_client_cls.return_value


def test_translates_rate_limit_error_into_reranker_unavailable(settings, mock_client) -> None:
    """The bug hit in production: a free-tier account without a payment
    method gets RateLimitError instead of a normal response. Before this,
    that propagated all the way up as an unhandled 500.
    """
    settings.VOYAGE_API_KEY = "test-key"
    mock_client.rerank.side_effect = voyageai.error.RateLimitError("reduced rate limits")

    with pytest.raises(RerankerUnavailableError):
        VoyageReranker().rerank("query", ["doc"], top_k=1)


def test_translates_service_unavailable_error(settings, mock_client) -> None:
    settings.VOYAGE_API_KEY = "test-key"
    mock_client.rerank.side_effect = voyageai.error.ServiceUnavailableError("down")

    with pytest.raises(RerankerUnavailableError):
        VoyageReranker().rerank("query", ["doc"], top_k=1)


def test_translates_timeout_error(settings, mock_client) -> None:
    settings.VOYAGE_API_KEY = "test-key"
    mock_client.rerank.side_effect = voyageai.error.Timeout("timed out")

    with pytest.raises(RerankerUnavailableError):
        VoyageReranker().rerank("query", ["doc"], top_k=1)


def test_does_not_swallow_unrelated_errors(settings, mock_client) -> None:
    """Only transient/availability errors get translated — a genuine bug
    in how we're calling the API (bad request, auth failure) should still
    surface loudly instead of silently degrading to unreranked results.
    """
    settings.VOYAGE_API_KEY = "test-key"
    mock_client.rerank.side_effect = voyageai.error.InvalidRequestError("bad request")

    with pytest.raises(voyageai.error.InvalidRequestError):
        VoyageReranker().rerank("query", ["doc"], top_k=1)


def test_returns_reranked_documents_on_success(settings, mock_client) -> None:
    settings.VOYAGE_API_KEY = "test-key"
    item = MagicMock(index=0, relevance_score=0.9)
    mock_client.rerank.return_value = MagicMock(results=[item])

    result = VoyageReranker().rerank("query", ["doc"], top_k=1)

    assert result[0].index == 0
    assert result[0].score == 0.9
