from rag.llm.factory import get_llm_provider
from rag.models import Conversation

REWRITE_SYSTEM_PROMPT = (
    "Rewrite the user's latest question into a standalone search query. Two "
    "separate things to do, both optional:\n"
    "1. If there is conversation history, resolve pronouns and implicit "
    'references (e.g. "the other one", "that approach") using it.\n'
    "2. If the question mentions a specific, unambiguous calendar date in "
    'any format ("July 21st 2025", "21 July 2025", "2025-07-21") — append '
    "its ISO 8601 form (YYYY-MM-DD) in parentheses. "
    "The notes being searched store every entry under an ISO-format date "
    "line, so a literal ISO date in the query measurably helps retrieval "
    "find the right day even when the question phrases it differently. Only "
    "do this for a date you can resolve with confidence — never guess at a "
    'relative date ("yesterday", "last Monday") without knowing today\'s '
    "date, and never invent a date that isn't actually in the question.\n"
    "Reply with ONLY the rewritten question itself, nothing else — not an "
    "answer to it. If neither rewrite applies, reply with the question "
    "unchanged."
)


def rewrite_query(conversation: Conversation, question: str) -> str:
    """Always makes one LLM call now, even for a conversation's first
    message — a deliberate cost trade-off. It used to skip entirely when
    there was no history (nothing to resolve pronouns against), but date
    normalization is just as relevant on a first message as a fifth: a
    real bug hit live showed hybrid search failing to match "July 21st
    2025" against notes that store the same day as "2025-07-21" — no
    literal text overlap between the two, and no conversation history
    involved at all. Measured afterwards over a sample of real dates:
    appending the ISO form moved two of them from "not in the top 5 at
    all" to the top hit, so this step earns its cost on its own, not
    only by feeding DateAwareRetriever.

    The history (when there is any) is flattened into a single user
    message rather than replayed as alternating user/assistant turns.
    Structuring it as a real multi-turn conversation invites the model to
    just *continue* the chat (i.e. answer the new question) instead of
    treating this as a one-off rewrite task — confirmed by hitting exactly
    that failure live: the model answered instead of rewriting, even
    though the system prompt said not to.
    """
    history = list(conversation.messages.order_by("created_at"))
    transcript = (
        "\n".join(f"{message.role}: {message.content}" for message in history)
        if history
        else "(no previous messages)"
    )
    prompt = (
        f"Conversation so far:\n{transcript}\n\n"
        f"Latest question: {question}\n\n"
        "Rewrite ONLY the latest question, following the system instructions."
    )

    result = get_llm_provider().chat(
        system=REWRITE_SYSTEM_PROMPT, messages=[{"role": "user", "content": prompt}]
    )
    return result.text.strip()
