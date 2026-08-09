from unittest.mock import patch

import pytest

from ingestion.factories import ChunkFactory
from rag.chat.service import ask, ask_with_contexts
from rag.factories import ConversationFactory
from rag.llm.base import ToolCallResult
from rag.llm.factory import get_llm_provider
from rag.models import Citation, Message
from rag.retrieval.base import RetrievalResult
from sources.factories import DocumentFactory

pytestmark = pytest.mark.django_db


class _StubRetriever:
    def __init__(self, results: list[RetrievalResult]) -> None:
        self._results = results

    def search(self, query, *, workspace_id, top_k=10, filters=None):
        return self._results


@pytest.fixture(autouse=True)
def _clear_llm_cache():
    get_llm_provider.cache_clear()
    yield
    get_llm_provider.cache_clear()


def _ask_with_stubbed_retrieval(conversation, question, results, tool_output):
    fake_llm = get_llm_provider()
    fake_llm.next_tool_result = ToolCallResult(
        output=tool_output, input_tokens=100, output_tokens=20
    )
    with patch("rag.chat.service.get_retriever", return_value=_StubRetriever(results)):
        return ask(conversation, question)


def test_ask_persists_both_the_user_and_assistant_messages() -> None:
    conversation = ConversationFactory()
    document = DocumentFactory(source__workspace=conversation.workspace)
    chunk = ChunkFactory(document=document, content="Hybrid search combines BM25 and embeddings.")

    message = _ask_with_stubbed_retrieval(
        conversation,
        "How does hybrid search work?",
        [RetrievalResult(chunk=chunk, score=1.0)],
        {"answer": "It combines BM25 with dense retrieval.", "cited_chunk_ids": [str(chunk.id)]},
    )

    assert conversation.messages.count() == 2
    user_message = conversation.messages.get(role=Message.Role.USER)
    assert user_message.content == "How does hybrid search work?"
    assert message.role == Message.Role.ASSISTANT
    assert message.content == "It combines BM25 with dense retrieval."


def test_ask_with_contexts_returns_the_retrieval_results_alongside_the_message() -> None:
    conversation = ConversationFactory()
    document = DocumentFactory(source__workspace=conversation.workspace)
    chunk = ChunkFactory(document=document, content="Hybrid search combines BM25 and embeddings.")
    results = [RetrievalResult(chunk=chunk, score=0.9)]

    fake_llm = get_llm_provider()
    fake_llm.next_tool_result = ToolCallResult(
        output={"answer": "It combines BM25 with dense retrieval.", "cited_chunk_ids": []},
        input_tokens=100,
        output_tokens=20,
    )
    with patch("rag.chat.service.get_retriever", return_value=_StubRetriever(results)):
        message, retrieved = ask_with_contexts(conversation, "How does hybrid search work?")

    assert message.content == "It combines BM25 with dense retrieval."
    # Not just the cited chunks (there are none here) -- every chunk
    # retrieval actually handed to the LLM as context.
    assert retrieved == results


def test_valid_citation_is_persisted() -> None:
    conversation = ConversationFactory()
    document = DocumentFactory(source__workspace=conversation.workspace)
    chunk = ChunkFactory(document=document, content="Real content that gets cited.")

    message = _ask_with_stubbed_retrieval(
        conversation,
        "question",
        [RetrievalResult(chunk=chunk, score=1.0)],
        {"answer": "An answer.", "cited_chunk_ids": [str(chunk.id)]},
    )

    assert Citation.objects.filter(message=message, chunk=chunk).exists()


def test_hallucinated_citation_is_never_persisted() -> None:
    """The core guarantee of citation validation: a chunk_id the model claims but
    that wasn't part of the context it was actually given never becomes a
    Citation row — not flagged, not stored anywhere, simply absent.
    """
    conversation = ConversationFactory()
    document = DocumentFactory(source__workspace=conversation.workspace)
    real_chunk = ChunkFactory(document=document, content="The only chunk actually retrieved.")
    fabricated_id = "00000000-0000-0000-0000-000000000000"

    message = _ask_with_stubbed_retrieval(
        conversation,
        "question",
        [RetrievalResult(chunk=real_chunk, score=1.0)],
        {
            "answer": "An answer citing something that was never provided.",
            "cited_chunk_ids": [str(real_chunk.id), fabricated_id],
        },
    )

    citations = list(message.citations.all())
    assert len(citations) == 1
    assert citations[0].chunk_id == real_chunk.id
    assert not Citation.objects.filter(chunk_id=fabricated_id).exists()


def test_records_latency_tokens_and_cost(settings) -> None:
    settings.LLM_COST_PER_MILLION_INPUT_TOKENS_USD = 1.0
    settings.LLM_COST_PER_MILLION_OUTPUT_TOKENS_USD = 5.0
    conversation = ConversationFactory()
    document = DocumentFactory(source__workspace=conversation.workspace)
    chunk = ChunkFactory(document=document, content="Some content.")

    message = _ask_with_stubbed_retrieval(
        conversation,
        "question",
        [RetrievalResult(chunk=chunk, score=1.0)],
        {"answer": "answer", "cited_chunk_ids": []},
    )

    assert message.latency_ms is not None
    assert message.input_tokens == 100
    assert message.output_tokens == 20
    # 100 * $1/M + 20 * $5/M = 0.0001 + 0.0001 = 0.0002
    assert float(message.cost) == pytest.approx(0.0002)


def test_works_with_no_retrieval_results() -> None:
    conversation = ConversationFactory()

    message = _ask_with_stubbed_retrieval(
        conversation,
        "question with nothing relevant indexed",
        [],
        {"answer": "I don't have notes about that.", "cited_chunk_ids": []},
    )

    assert message.content == "I don't have notes about that."
    assert not message.citations.exists()


def test_titles_the_conversation_after_its_first_question() -> None:
    conversation = ConversationFactory(title="")

    _ask_with_stubbed_retrieval(
        conversation, "What did I do in July?", [], {"answer": "a", "cited_chunk_ids": []}
    )

    conversation.refresh_from_db()
    assert conversation.title == "What did I do in July?"


def test_does_not_retitle_the_conversation_on_later_questions() -> None:
    conversation = ConversationFactory(title="")

    _ask_with_stubbed_retrieval(
        conversation, "First question", [], {"answer": "a", "cited_chunk_ids": []}
    )
    _ask_with_stubbed_retrieval(
        conversation, "Second question", [], {"answer": "b", "cited_chunk_ids": []}
    )

    conversation.refresh_from_db()
    assert conversation.title == "First question"


def test_truncates_a_long_first_question_into_the_title() -> None:
    conversation = ConversationFactory(title="")
    question = "word " * 40

    _ask_with_stubbed_retrieval(conversation, question, [], {"answer": "a", "cited_chunk_ids": []})

    conversation.refresh_from_db()
    assert len(conversation.title) <= 60
    assert conversation.title.endswith("…")


def test_citations_record_their_retrieval_rank_and_score() -> None:
    conversation = ConversationFactory()
    document = DocumentFactory(source__workspace=conversation.workspace)
    top, second = (
        ChunkFactory(document=document, content="first"),
        ChunkFactory(document=document, content="second"),
    )
    results = [
        RetrievalResult(chunk=top, score=0.91),
        RetrievalResult(chunk=second, score=0.42),
    ]

    message = _ask_with_stubbed_retrieval(
        conversation,
        "q",
        results,
        {"answer": "a", "cited_chunk_ids": [str(second.id), str(top.id)]},
    )

    citations = list(message.citations.all())
    # Ordered by retrieval position, not by the order the model listed
    # them — the model cited the second chunk first here.
    assert [c.chunk_id for c in citations] == [top.id, second.id]
    assert [c.rank for c in citations] == [1, 2]
    assert citations[0].score == pytest.approx(0.91)
    assert citations[1].score == pytest.approx(0.42)


def test_citation_rank_reflects_position_in_the_full_context() -> None:
    """A chunk retrieved third keeps rank 3 even when the two above it
    were never cited — the number means "how the retriever ranked this",
    which is only true if it survives the model's selection.
    """
    conversation = ConversationFactory()
    document = DocumentFactory(source__workspace=conversation.workspace)
    chunks = [ChunkFactory(document=document, content=f"c{i}") for i in range(3)]
    results = [RetrievalResult(chunk=c, score=1.0 - i / 10) for i, c in enumerate(chunks)]

    message = _ask_with_stubbed_retrieval(
        conversation, "q", results, {"answer": "a", "cited_chunk_ids": [str(chunks[2].id)]}
    )

    citation = message.citations.get()
    assert citation.rank == 3
