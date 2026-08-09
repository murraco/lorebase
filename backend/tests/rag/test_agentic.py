from unittest.mock import patch

import pytest

from ingestion.factories import ChunkFactory
from rag.chat.agentic import ask_agentic
from rag.chat.prompting import ANSWER_TOOL
from rag.factories import ConversationFactory
from rag.llm.base import AgentStepResult, ToolCallResult
from rag.llm.factory import get_llm_provider
from rag.models import Message
from rag.retrieval.base import RetrievalResult
from sources.factories import DocumentFactory

pytestmark = pytest.mark.django_db


class _StubRetriever:
    """Keyed by query, not a single fixed list: the whole point of the
    agentic path is that different searches can return different results.
    """

    def __init__(self, results_by_query: dict[str, list[RetrievalResult]]) -> None:
        self._results_by_query = results_by_query

    def search(self, query, *, workspace_id, top_k=10, filters=None):
        return self._results_by_query.get(query, [])


def _answer_step(*, answer: str, cited_chunk_ids: list[str]) -> AgentStepResult:
    return AgentStepResult(
        tool_name=ANSWER_TOOL.name,
        tool_input={"answer": answer, "cited_chunk_ids": cited_chunk_ids},
        tool_use_id="tool_use_answer",
        raw_assistant_content=[{"type": "tool_use", "name": ANSWER_TOOL.name}],
        input_tokens=50,
        output_tokens=10,
    )


def _search_step(*, query: str, tool_use_id: str = "tool_use_search") -> AgentStepResult:
    return AgentStepResult(
        tool_name="search_knowledge",
        tool_input={"query": query},
        tool_use_id=tool_use_id,
        raw_assistant_content=[{"type": "tool_use", "name": "search_knowledge"}],
        input_tokens=30,
        output_tokens=5,
    )


@pytest.fixture(autouse=True)
def _clear_llm_cache():
    get_llm_provider.cache_clear()
    yield
    get_llm_provider.cache_clear()


def test_ask_agentic_searches_once_then_answers() -> None:
    conversation = ConversationFactory()
    document = DocumentFactory(source__workspace=conversation.workspace)
    chunk = ChunkFactory(document=document, content="Hybrid search combines BM25 and embeddings.")
    retriever = _StubRetriever({"hybrid search": [RetrievalResult(chunk=chunk, score=0.9)]})

    fake_llm = get_llm_provider()
    fake_llm.next_agent_steps = [
        _search_step(query="hybrid search"),
        _answer_step(answer="It combines BM25 with embeddings.", cited_chunk_ids=[str(chunk.id)]),
    ]

    with patch("rag.chat.agentic.get_retriever", return_value=retriever):
        message, results = ask_agentic(conversation, "How does hybrid search work?")

    assert message.content == "It combines BM25 with embeddings."
    assert message.citations.count() == 1
    assert [r.chunk.id for r in results] == [chunk.id]
    # Tokens summed across both LLM turns (search decision + answer), not
    # just the final one -- this is the real cost of the whole turn.
    assert message.input_tokens == 30 + 50
    assert message.output_tokens == 5 + 10


def test_ask_agentic_supports_more_than_one_search() -> None:
    conversation = ConversationFactory()
    document = DocumentFactory(source__workspace=conversation.workspace)
    first_chunk = ChunkFactory(document=document, content="ACH settles asynchronously.")
    second_chunk = ChunkFactory(document=document, content="The rollout used a per-user cohort.")
    retriever = _StubRetriever(
        {
            "ACH migration": [RetrievalResult(chunk=first_chunk, score=0.8)],
            "ACH rollout safety": [RetrievalResult(chunk=second_chunk, score=0.85)],
        }
    )

    fake_llm = get_llm_provider()
    fake_llm.next_agent_steps = [
        _search_step(query="ACH migration", tool_use_id="t1"),
        _search_step(query="ACH rollout safety", tool_use_id="t2"),
        _answer_step(
            answer="It rolled out safely via a per-user cohort.",
            cited_chunk_ids=[str(first_chunk.id), str(second_chunk.id)],
        ),
    ]

    with patch("rag.chat.agentic.get_retriever", return_value=retriever):
        message, results = ask_agentic(conversation, "How did the ACH migration roll out safely?")

    assert {r.chunk.id for r in results} == {first_chunk.id, second_chunk.id}
    assert message.citations.count() == 2
    # Citation rank reflects the order chunks were first found across
    # searches, same "how the retriever ranked this" contract as ask().
    ranks = {c.chunk_id: c.rank for c in message.citations.all()}
    assert ranks[first_chunk.id] == 1
    assert ranks[second_chunk.id] == 2


def test_ask_agentic_deduplicates_a_chunk_found_by_more_than_one_search() -> None:
    conversation = ConversationFactory()
    document = DocumentFactory(source__workspace=conversation.workspace)
    chunk = ChunkFactory(document=document, content="Shared content both searches surface.")
    retriever = _StubRetriever(
        {
            "first angle": [RetrievalResult(chunk=chunk, score=0.7)],
            "second angle": [RetrievalResult(chunk=chunk, score=0.9)],
        }
    )

    fake_llm = get_llm_provider()
    fake_llm.next_agent_steps = [
        _search_step(query="first angle", tool_use_id="t1"),
        _search_step(query="second angle", tool_use_id="t2"),
        _answer_step(answer="An answer.", cited_chunk_ids=[str(chunk.id)]),
    ]

    with patch("rag.chat.agentic.get_retriever", return_value=retriever):
        message, results = ask_agentic(conversation, "A question needing two angles.")

    assert len(results) == 1
    assert message.retrieved_count == 1


def test_ask_agentic_drops_a_citation_for_a_chunk_never_actually_retrieved() -> None:
    conversation = ConversationFactory()
    document = DocumentFactory(source__workspace=conversation.workspace)
    chunk = ChunkFactory(document=document)
    retriever = _StubRetriever({"q": [RetrievalResult(chunk=chunk, score=0.9)]})

    fake_llm = get_llm_provider()
    fake_llm.next_agent_steps = [
        _search_step(query="q"),
        _answer_step(answer="An answer.", cited_chunk_ids=[str(chunk.id), "not-a-real-chunk-id"]),
    ]

    with patch("rag.chat.agentic.get_retriever", return_value=retriever):
        message, _results = ask_agentic(conversation, "A question.")

    assert [c.chunk_id for c in message.citations.all()] == [chunk.id]


def test_ask_agentic_forces_an_answer_after_max_iterations() -> None:
    conversation = ConversationFactory()
    document = DocumentFactory(source__workspace=conversation.workspace)
    chunk = ChunkFactory(document=document)
    retriever = _StubRetriever({"q": [RetrievalResult(chunk=chunk, score=0.5)]})

    fake_llm = get_llm_provider()
    # Never calls provide_answer on its own -- 5 search steps exhausts
    # _MAX_ITERATIONS, so a 6th, forced stream_tool call must produce the
    # final answer instead of the turn ending with no Message content.
    fake_llm.next_agent_steps = [_search_step(query="q", tool_use_id=f"t{i}") for i in range(5)]
    fake_llm.next_tool_result = ToolCallResult(
        output={"answer": "Forced answer.", "cited_chunk_ids": [str(chunk.id)]},
        input_tokens=40,
        output_tokens=8,
    )

    with patch("rag.chat.agentic.get_retriever", return_value=retriever):
        message, _results = ask_agentic(
            conversation, "A question the model won't stop searching for."
        )

    assert message.content == "Forced answer."
    assert message.citations.count() == 1


def test_ask_agentic_persists_the_user_message_too() -> None:
    conversation = ConversationFactory()
    document = DocumentFactory(source__workspace=conversation.workspace)
    chunk = ChunkFactory(document=document)
    retriever = _StubRetriever({"q": [RetrievalResult(chunk=chunk, score=0.5)]})

    fake_llm = get_llm_provider()
    fake_llm.next_agent_steps = [
        _search_step(query="q"),
        _answer_step(answer="An answer.", cited_chunk_ids=[]),
    ]

    with patch("rag.chat.agentic.get_retriever", return_value=retriever):
        ask_agentic(conversation, "A question.")

    assert conversation.messages.filter(role=Message.Role.USER, content="A question.").exists()
