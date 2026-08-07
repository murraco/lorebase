import time
from decimal import Decimal

from django.conf import settings
from django.db import transaction

from rag.chat.prompting import ANSWER_TOOL, SYSTEM_PROMPT, build_context
from rag.chat.rewriting import rewrite_query
from rag.llm.factory import get_llm_provider
from rag.models import Citation, Conversation, Message
from rag.retrieval.factory import get_retriever


def ask(conversation: Conversation, question: str) -> Message:
    """The end-to-end RAG turn: rewrite (if there's history) -> retrieve
    -> build a prompt out of the *actually retrieved* chunks -> force a
    structured answer -> keep only citations that were genuinely part of
    that context -> persist. Nothing before "force a structured answer"
    touches the LLM except the optional rewrite step.
    """
    Message.objects.create(conversation=conversation, role=Message.Role.USER, content=question)

    search_query = rewrite_query(conversation, question)
    results = get_retriever().search(search_query, workspace_id=conversation.workspace_id, top_k=5)

    context = build_context(results)
    chunks_by_id = {str(result.chunk.id): result.chunk for result in results}
    user_content = f"{context}\n\nQuestion: {question}" if results else f"Question: {question}"

    start = time.monotonic()
    result = get_llm_provider().stream_tool(
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
        tool=ANSWER_TOOL,
    )
    latency_ms = int((time.monotonic() - start) * 1000)

    answer_text = str(result.output.get("answer", ""))
    claimed_chunk_ids = result.output.get("cited_chunk_ids", [])
    # The one place hallazgo 7 actually gets enforced: only chunk_ids that
    # were genuinely part of the context we just sent survive. Anything
    # else — a typo'd id, a chunk cited from an earlier turn, a plausible
    # guess — is silently dropped, never persisted as a Citation.
    validated_chunk_ids = [
        chunk_id for chunk_id in claimed_chunk_ids if chunk_id in chunks_by_id
    ]

    with transaction.atomic():
        message = Message.objects.create(
            conversation=conversation,
            role=Message.Role.ASSISTANT,
            content=answer_text,
            latency_ms=latency_ms,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            cost=_estimate_cost(result.input_tokens, result.output_tokens),
        )
        Citation.objects.bulk_create(
            Citation(message=message, chunk=chunks_by_id[chunk_id])
            for chunk_id in validated_chunk_ids
        )
    return message


def _estimate_cost(input_tokens: int, output_tokens: int) -> Decimal | None:
    input_rate = settings.LLM_COST_PER_MILLION_INPUT_TOKENS_USD
    output_rate = settings.LLM_COST_PER_MILLION_OUTPUT_TOKENS_USD
    if not input_rate and not output_rate:
        return None
    cost = (input_tokens * Decimal(str(input_rate)) + output_tokens * Decimal(str(output_rate)))
    return cost / Decimal("1_000_000")
