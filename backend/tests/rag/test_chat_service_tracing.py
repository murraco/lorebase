from unittest.mock import patch

import pytest

from ingestion.factories import ChunkFactory
from rag.chat.service import ask
from rag.factories import ConversationFactory
from rag.llm.base import ToolCallResult
from rag.llm.factory import get_llm_provider
from rag.retrieval.base import RetrievalResult
from sources.factories import DocumentFactory

pytestmark = pytest.mark.django_db


class _StubRetriever:
    """Not @traced_search-decorated on purpose — this suite is about
    rag.ask()'s own spans, not retrieval's (see test_retrieval_tracing.py
    for that). A plain stub keeps the span tree this asserts against
    small and unambiguous.
    """

    def __init__(self, results: list[RetrievalResult]) -> None:
        self._results = results

    def search(self, query, *, workspace_id, top_k=10, filters=None):
        return self._results


@pytest.fixture(autouse=True)
def _clear_llm_cache():
    get_llm_provider.cache_clear()
    yield
    get_llm_provider.cache_clear()


def test_ask_records_a_turn_span_with_a_nested_llm_call_span(otel_spans) -> None:
    conversation = ConversationFactory()
    document = DocumentFactory(source__workspace=conversation.workspace)
    chunk = ChunkFactory(document=document, content="Some content.")

    fake_llm = get_llm_provider()
    fake_llm.next_tool_result = ToolCallResult(
        output={"answer": "An answer.", "cited_chunk_ids": [str(chunk.id)]},
        input_tokens=100,
        output_tokens=20,
    )
    with patch(
        "rag.chat.service.get_retriever",
        return_value=_StubRetriever([RetrievalResult(chunk=chunk, score=0.9)]),
    ):
        ask(conversation, "What does the note say?")

    spans = {span.name: span for span in otel_spans.get_finished_spans()}
    assert set(spans) == {"rag.ask", "rag.rewrite_query", "rag.llm_call"}

    turn_span = spans["rag.ask"]
    assert turn_span.attributes["lorebase.retrieved_count"] == 1
    assert turn_span.attributes["lorebase.citations_count"] == 1

    llm_span = spans["rag.llm_call"]
    assert llm_span.parent.span_id == turn_span.context.span_id
    assert llm_span.attributes["gen_ai.provider.name"] == "fake"
    assert llm_span.attributes["gen_ai.usage.input_tokens"] == 100
    assert llm_span.attributes["gen_ai.usage.output_tokens"] == 20

    rewrite_span = spans["rag.rewrite_query"]
    assert rewrite_span.parent.span_id == turn_span.context.span_id


def test_llm_call_span_has_no_cost_attribute_when_cost_is_not_configured(
    otel_spans, settings
) -> None:
    """_estimate_cost() returns None when no cost-per-token setting is
    configured — the span must not claim a cost of $0, which would look
    like a real, verified number instead of "unknown"."""
    settings.LLM_COST_PER_MILLION_INPUT_TOKENS_USD = 0.0
    settings.LLM_COST_PER_MILLION_OUTPUT_TOKENS_USD = 0.0
    conversation = ConversationFactory()

    fake_llm = get_llm_provider()
    fake_llm.next_tool_result = ToolCallResult(
        output={"answer": "An answer.", "cited_chunk_ids": []}, input_tokens=10, output_tokens=5
    )
    with patch("rag.chat.service.get_retriever", return_value=_StubRetriever([])):
        ask(conversation, "A question with no configured cost.")

    llm_span = next(s for s in otel_spans.get_finished_spans() if s.name == "rag.llm_call")
    assert "lorebase.cost_usd" not in llm_span.attributes
