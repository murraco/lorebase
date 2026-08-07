import math

from rag.embeddings.fake import FakeEmbeddingProvider


def test_same_text_always_produces_the_same_vector() -> None:
    provider = FakeEmbeddingProvider(dimensions=16)

    first = provider.embed_query("hello world")
    second = provider.embed_query("hello world")

    assert first == second


def test_different_text_produces_different_vectors() -> None:
    provider = FakeEmbeddingProvider(dimensions=16)

    a = provider.embed_query("hello")
    b = provider.embed_query("goodbye")

    assert a != b


def test_vectors_have_the_configured_dimensions() -> None:
    provider = FakeEmbeddingProvider(dimensions=32)

    vector = provider.embed_query("some text")

    assert len(vector) == 32
    assert provider.dimensions == 32


def test_vectors_are_unit_normalized() -> None:
    provider = FakeEmbeddingProvider(dimensions=16)

    vector = provider.embed_query("some text")
    norm = math.sqrt(sum(v * v for v in vector))

    assert math.isclose(norm, 1.0, rel_tol=1e-9)


def test_embed_documents_matches_embed_query_per_text() -> None:
    """Both methods hash the same way — deterministic wrt the text alone,
    not which method was called (real providers only differ by input_type,
    which the fake has no way to reflect deterministically)."""
    provider = FakeEmbeddingProvider(dimensions=16)

    from_query = provider.embed_query("same text")
    (from_documents,) = provider.embed_documents(["same text"])

    assert from_query == from_documents
