import json
from unittest.mock import patch

import pytest

from ingestion.factories import ChunkFactory
from rag.chat.streaming import _serialize_citations, stream_chat_response
from rag.factories import ConversationFactory
from rag.llm.base import ToolCallResult
from rag.llm.factory import get_llm_provider
from rag.models import Citation, Message
from rag.retrieval.base import RetrievalResult
from rag.serializers import CitationSerializer
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


def test_streamed_citations_match_the_api_serializer_fields() -> None:
    """The two paths that deliver a citation must agree on its shape.

    They drifted once: the stream sent `chunk_id` and no `id`, while the
    API sent `id`. The client types both against the same generated
    `Citation`, so nothing failed until an answer cited more than one
    chunk and the UI's track-by-id collapsed on duplicate undefined keys.
    """
    conversation = ConversationFactory()
    document = DocumentFactory(source__workspace=conversation.workspace)
    chunk = ChunkFactory(document=document)
    message = Message.objects.create(
        conversation=conversation, role=Message.Role.ASSISTANT, content="answer"
    )
    Citation.objects.create(message=message, chunk=chunk, rank=1, score=0.5)

    streamed = _serialize_citations(message)[0]
    serialized = CitationSerializer(message.citations.get()).data

    assert set(streamed) == set(serialized)


def test_streamed_citations_have_unique_ids() -> None:
    """What the UI tracks on. Several citations sharing a key is what
    made them vanish rather than merely render oddly.
    """
    conversation = ConversationFactory()
    document = DocumentFactory(source__workspace=conversation.workspace)
    message = Message.objects.create(
        conversation=conversation, role=Message.Role.ASSISTANT, content="answer"
    )
    for rank in range(1, 4):
        Citation.objects.create(
            message=message, chunk=ChunkFactory(document=document), rank=rank, score=0.5
        )

    ids = [citation["id"] for citation in _serialize_citations(message)]

    assert len(ids) == 3
    assert len(set(ids)) == 3
    assert all(ids)
