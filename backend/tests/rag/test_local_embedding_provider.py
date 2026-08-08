from unittest.mock import patch

from rag.embeddings.local import LocalEmbeddingProvider


class _FakeArray(list):
    """Stands in for a numpy array: sentence-transformers' encode()
    returns one, and only .tolist() is ever called on the result here.
    """

    def tolist(self):
        return list(self)


def test_embed_documents_prefixes_with_passage() -> None:
    with patch("sentence_transformers.SentenceTransformer") as mock_cls:
        mock_cls.return_value.encode.return_value = _FakeArray([[0.1, 0.2]])

        LocalEmbeddingProvider().embed_documents(["hello"])

    mock_cls.return_value.encode.assert_called_once_with(
        ["passage: hello"], normalize_embeddings=True
    )


def test_embed_query_prefixes_with_query() -> None:
    with patch("sentence_transformers.SentenceTransformer") as mock_cls:
        mock_cls.return_value.encode.return_value = _FakeArray([0.1, 0.2])

        LocalEmbeddingProvider().embed_query("hello")

    mock_cls.return_value.encode.assert_called_once_with("query: hello", normalize_embeddings=True)


def test_loads_the_model_only_once_across_multiple_calls() -> None:
    with patch("sentence_transformers.SentenceTransformer") as mock_cls:
        mock_cls.return_value.encode.return_value = _FakeArray([[0.1]])
        provider = LocalEmbeddingProvider()

        provider.embed_documents(["a"])
        provider.embed_documents(["b"])

    assert mock_cls.call_count == 1


def test_uses_the_configured_model_name(settings) -> None:
    settings.LOCAL_EMBEDDING_MODEL = "some/other-model"

    with patch("sentence_transformers.SentenceTransformer") as mock_cls:
        mock_cls.return_value.encode.return_value = _FakeArray([[0.1]])
        LocalEmbeddingProvider().embed_documents(["a"])

    mock_cls.assert_called_once_with("some/other-model")


def test_dimensions_reports_the_configured_setting(settings) -> None:
    settings.EMBEDDING_DIMENSIONS = 1024

    assert LocalEmbeddingProvider().dimensions == 1024
