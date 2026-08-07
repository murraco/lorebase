from rag.llm.factory import get_llm_provider
from rag.models import Conversation

REWRITE_SYSTEM_PROMPT = (
    "Rewrite the user's latest question into a standalone question that "
    "makes sense without the conversation history — resolve pronouns and "
    "implicit references (e.g. \"the other one\", \"that approach\") using "
    "the history. Reply with ONLY the rewritten question itself, nothing "
    "else — not an answer to it. If the question is already standalone, "
    "reply with it unchanged."
)


def rewrite_query(conversation: Conversation, question: str) -> str:
    """A standalone question doesn't need rewriting — and skipping the
    call for a conversation's first message avoids paying for an LLM call
    with nothing to resolve against.

    The history is flattened into a single user message rather than
    replayed as alternating user/assistant turns. Structuring it as a real
    multi-turn conversation invites the model to just *continue* the chat
    (i.e. answer the new question) instead of treating this as a one-off
    rewrite task — confirmed by hitting exactly that failure live: the
    model answered instead of rewriting, even though the system prompt
    said not to.
    """
    history = list(conversation.messages.order_by("created_at"))
    if not history:
        return question

    transcript = "\n".join(f"{message.role}: {message.content}" for message in history)
    prompt = (
        f"Conversation so far:\n{transcript}\n\n"
        f"Latest question: {question}\n\n"
        "Rewrite ONLY the latest question into a standalone version."
    )

    result = get_llm_provider().chat(
        system=REWRITE_SYSTEM_PROMPT, messages=[{"role": "user", "content": prompt}]
    )
    return result.text.strip()
