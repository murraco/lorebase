import pytest

from rag.chat.rewriting import rewrite_query
from rag.factories import ConversationFactory
from rag.llm.base import ChatResult
from rag.llm.factory import get_llm_provider
from rag.models import Message

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _clear_llm_cache():
    get_llm_provider.cache_clear()
    yield
    get_llm_provider.cache_clear()


def test_first_message_still_gets_rewritten_for_date_normalization() -> None:
    """No history to resolve pronouns against, but the rewrite step also
    normalizes dates mentioned in the question itself — just as relevant
    on a first message as a fifth, so this no longer skips the LLM call.
    """
    conversation = ConversationFactory()
    fake_llm = get_llm_provider()
    fake_llm.next_chat_result = ChatResult(
        text="What did I do on July 21st 2025 (2025-07-21)?",
        input_tokens=10,
        output_tokens=5,
    )

    result = rewrite_query(conversation, "What did I do on July 21st 2025?")

    assert result == "What did I do on July 21st 2025 (2025-07-21)?"
    assert len(fake_llm.calls) == 1
    assert fake_llm.calls[0].messages[0]["role"] == "user"
    assert "(no previous messages)" in fake_llm.calls[0].messages[0]["content"]


def test_follow_up_message_gets_rewritten_using_history() -> None:
    conversation = ConversationFactory()
    Message.objects.create(
        conversation=conversation, role=Message.Role.USER, content="What is RRF?"
    )
    Message.objects.create(
        conversation=conversation,
        role=Message.Role.ASSISTANT,
        content="RRF combines rankings from lexical and dense search.",
    )
    fake_llm = get_llm_provider()
    fake_llm.next_chat_result = ChatResult(
        text="What is the k constant in Reciprocal Rank Fusion?",
        input_tokens=10,
        output_tokens=5,
    )

    result = rewrite_query(conversation, "what about the k constant?")

    assert result == "What is the k constant in Reciprocal Rank Fusion?"
    assert len(fake_llm.calls) == 1
    call = fake_llm.calls[0]
    assert call.kind == "chat"
    # Regression guard for a real failure hit manually: history replayed
    # as alternating user/assistant turns reads as an ongoing chat, and
    # the model answered the new question instead of rewriting it. A
    # single flattened message can't be mistaken for "keep chatting".
    assert len(call.messages) == 1
    assert call.messages[0]["role"] == "user"
    assert "What is RRF?" in call.messages[0]["content"]
    assert "what about the k constant?" in call.messages[0]["content"]
