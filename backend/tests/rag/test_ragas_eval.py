from unittest.mock import patch

import pytest
from ragas.embeddings.base import LangchainEmbeddingsWrapper
from ragas.llms.base import LangchainLLMWrapper
from ragas.metrics import (
    Faithfulness,
    LLMContextPrecisionWithReference,
    LLMContextRecall,
    ResponseRelevancy,
)

from rag.evaluation.ragas_eval import (
    _build_embeddings,
    _build_llm,
    _EmbeddingProviderAdapter,
    build_metrics,
    build_sample,
    run_evaluation,
)


@pytest.fixture(autouse=True)
def _clear_caches():
    _build_llm.cache_clear()
    _build_embeddings.cache_clear()
    yield
    _build_llm.cache_clear()
    _build_embeddings.cache_clear()


def test_embedding_adapter_delegates_to_the_configured_provider(settings) -> None:
    settings.EMBEDDING_PROVIDER = "fake"
    settings.EMBEDDING_DIMENSIONS = 8
    adapter = _EmbeddingProviderAdapter()

    query_vector = adapter.embed_query("what happened on the 21st")
    (doc_vector,) = adapter.embed_documents(["some chunk content"])

    assert len(query_vector) == 8
    assert len(doc_vector) == 8
    # Deterministic (FakeEmbeddingProvider seeds from the text itself), so
    # this is really asserting the adapter didn't silently transform
    # anything -- same text in, same vector as calling the provider directly.
    from rag.embeddings.fake import FakeEmbeddingProvider

    expected = FakeEmbeddingProvider(dimensions=8).embed_query("what happened on the 21st")
    assert query_vector == expected


def test_build_sample_maps_fields_onto_a_single_turn_sample() -> None:
    sample = build_sample(
        question="What does the note say?",
        retrieved_contexts=["chunk one", "chunk two"],
        response="An answer.",
        reference="The expected answer.",
    )

    assert sample.user_input == "What does the note say?"
    assert sample.retrieved_contexts == ["chunk one", "chunk two"]
    assert sample.response == "An answer."
    assert sample.reference == "The expected answer."


def test_build_metrics_returns_the_four_pinned_metrics_wired_with_llm(settings) -> None:
    settings.EMBEDDING_PROVIDER = "fake"
    settings.EMBEDDING_DIMENSIONS = 8

    metrics = build_metrics()

    assert [type(m) for m in metrics] == [
        LLMContextPrecisionWithReference,
        LLMContextRecall,
        Faithfulness,
        ResponseRelevancy,
    ]
    assert all(isinstance(m.llm, LangchainLLMWrapper) for m in metrics)
    assert isinstance(metrics[-1].embeddings, LangchainEmbeddingsWrapper)


def test_build_llm_and_embeddings_are_memoized(settings) -> None:
    settings.EMBEDDING_PROVIDER = "fake"
    settings.EMBEDDING_DIMENSIONS = 8

    assert _build_llm() is _build_llm()
    assert _build_embeddings() is _build_embeddings()


def test_run_evaluation_scores_the_dataset_with_the_four_metrics(settings) -> None:
    """Doesn't hit a real judge LLM: patches ragas.evaluate itself, so this
    only asserts run_evaluation wires the dataset and metric list
    correctly -- the metrics' actual judgment behavior is ragas's own
    responsibility, not this codebase's to test.
    """
    settings.EMBEDDING_PROVIDER = "fake"
    settings.EMBEDDING_DIMENSIONS = 8
    sample = build_sample(
        question="q", retrieved_contexts=["ctx"], response="resp", reference="ref"
    )

    with patch("rag.evaluation.ragas_eval.evaluate") as mock_evaluate:
        run_evaluation([sample])

    (call,) = mock_evaluate.call_args_list
    (dataset,) = call.args
    assert dataset.samples == [sample]
    assert len(call.kwargs["metrics"]) == 4
