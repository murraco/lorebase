from unittest.mock import patch

import pytest

from rag.reranking.local import LocalReranker


def test_returns_reranked_documents_ordered_by_score() -> None:
    with patch("sentence_transformers.CrossEncoder") as mock_cls:
        mock_cls.return_value.predict.return_value = [0.2, 0.9, 0.5]

        result = LocalReranker().rerank("query", ["doc0", "doc1", "doc2"], top_k=2)

    assert [item.index for item in result] == [1, 2]
    assert result[0].score == pytest.approx(0.9)


def test_loads_the_model_only_once_across_multiple_reranks() -> None:
    with patch("sentence_transformers.CrossEncoder") as mock_cls:
        mock_cls.return_value.predict.return_value = [0.1]
        reranker = LocalReranker()

        reranker.rerank("q", ["a"], top_k=1)
        reranker.rerank("q", ["a"], top_k=1)

    assert mock_cls.call_count == 1


def test_empty_documents_returns_empty_without_loading_the_model() -> None:
    with patch("sentence_transformers.CrossEncoder") as mock_cls:
        result = LocalReranker().rerank("query", [], top_k=5)

    assert result == []
    mock_cls.assert_not_called()


def test_uses_the_configured_model_name(settings) -> None:
    settings.LOCAL_RERANK_MODEL = "some/other-model"

    with patch("sentence_transformers.CrossEncoder") as mock_cls:
        mock_cls.return_value.predict.return_value = [0.5]
        LocalReranker().rerank("q", ["a"], top_k=1)

    mock_cls.assert_called_once_with("some/other-model")
