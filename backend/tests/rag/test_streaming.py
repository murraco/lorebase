import json
from unittest.mock import patch

import pytest

from ingestion.factories import ChunkFactory
from rag.chat.streaming import stream_chat_response
from rag.factories import ConversationFactory
from rag.llm.base import ToolCallResult
from rag.llm.factory import get_llm_provider
from rag.retrieval.base import RetrievalResult
from sources.factories import DocumentFactory

pytestmark = pytest.mark.django_db


class _StubRetriever:
    def __init__(self, results):
        self._results = results

    def search(self, query, *, workspace_id, top_k=10, filters=None):
        return self._results


@pytest.fixture(autouse=True)
def _clear_llm_cache():
    get_llm_provider.cache_clear()
    yield
    get_llm_provider.cache_clear()


def test_stream_yields_the_answer_then_a_done_event_with_citations() -> None:
    conversation = ConversationFactory()
    document = DocumentFactory(source__workspace=conversation.workspace)
    chunk = ChunkFactory(document=document, content="content", start_line=3, end_line=7)

    fake_llm = get_llm_provider()
    fake_llm.next_tool_result = ToolCallResult(
        output={"answer": "two words", "cited_chunk_ids": [str(chunk.id)]},
        input_tokens=10,
        output_tokens=5,
    )

    with patch(
        "rag.chat.service.get_retriever",
        return_value=_StubRetriever([RetrievalResult(chunk=chunk, score=1.0)]),
    ):
        response = stream_chat_response(conversation, "question")
        events = [chunk.decode() for chunk in response.streaming_content]

    assert response["Content-Type"] == "text/event-stream"
    *delta_events, done_event = events

    deltas = [json.loads(e.removeprefix("data: ").strip())["delta"] for e in delta_events]
    assert "".join(deltas).strip() == "two words"

    done_payload = json.loads(done_event.removeprefix("data: ").strip())
    assert done_payload["done"] is True
    assert len(done_payload["citations"]) == 1
    assert done_payload["citations"][0]["path"] == document.path
    assert done_payload["citations"][0]["start_line"] == 3
    assert done_payload["citations"][0]["end_line"] == 7
