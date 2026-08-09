import time
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from opentelemetry import trace
from opentelemetry.semconv._incubating.attributes import gen_ai_attributes as gen_ai

from rag.chat.prompting import ANSWER_TOOL, SYSTEM_PROMPT, build_context
from rag.chat.rewriting import rewrite_query
from rag.llm.factory import get_llm_provider
from rag.models import Citation, Conversation, Message
from rag.retrieval.base import RetrievalResult
from rag.retrieval.factory import get_retriever

_tracer = trace.get_tracer("lorebase.chat")


def ask(conversation: Conversation, question: str) -> Message:
    """The end-to-end RAG turn -- see _ask() for what it actually does.
    Public callers only ever need the persisted Message; ask_with_contexts()
    exists alongside this for the one caller (the evaluation harness) that
    also needs to know what was retrieved.
    """
    message, _results = _ask(conversation, question)
    return message


def ask_with_contexts(
    conversation: Conversation, question: str
) -> tuple[Message, list[RetrievalResult]]:
    """Like ask(), but also returns the retrieval results actually fed to
    the LLM as context -- RAGAS calls the chunk text retrieved_contexts,
    and it's also how the evaluation harness checks a golden-set
    question's expected_document/expected_heading were really among them.
    Returning RetrievalResult (chunk + score) rather than plain strings
    keeps both uses possible from one call: the harness needs
    result.chunk.content for RAGAS and result.chunk.document.title /
    result.chunk.heading_path for the hit check.
    """
    return _ask(conversation, question)


def _ask(conversation: Conversation, question: str) -> tuple[Message, list[RetrievalResult]]:
    """rewrite (if there's history) -> retrieve -> build a prompt out of
    the *actually retrieved* chunks -> force a structured answer -> keep
    only citations that were genuinely part of that context -> persist.
    Nothing before "force a structured answer" touches the LLM except the
    optional rewrite step.

    Worth being explicit about what this does NOT do: the answer call
    below is given only the retrieved context and the current question —
    never the conversation's previous turns. The LLM answering has no
    memory of what it just said; all conversational continuity lives in
    rewrite_query(), which does read the full history to resolve
    references before retrieval. That keeps cost and latency flat per
    turn regardless of conversation length, and keeps citation validation
    trivially sound (chunks_by_id only ever holds this turn's context, so
    an id carried over from an earlier turn can't validate). The cost is
    that the assistant can't refer back to its own earlier answers.
    """
    with _tracer.start_as_current_span("rag.ask") as turn_span:
        turn_span.set_attribute("lorebase.conversation_id", str(conversation.id))

        _set_title_if_first_message(conversation, question)
        Message.objects.create(conversation=conversation, role=Message.Role.USER, content=question)

        with _tracer.start_as_current_span("rag.rewrite_query"):
            search_query = rewrite_query(conversation, question)

        # No span of its own here: get_retriever() returns a chain of
        # Retriever wrappers each already decorated with @traced_search
        # (rag/retrieval/tracing.py), so this one call already produces a
        # full nested span tree for whatever strategy is configured.
        results = get_retriever().search(
            search_query, workspace_id=conversation.workspace_id, top_k=5
        )

        context = build_context(results)
        chunks_by_id = {str(result.chunk.id): result.chunk for result in results}
        # Retrieval provenance, keyed the same way, so a citation can carry
        # where the chunk placed and what it scored. Captured here because
        # `results` is the only place that knows it — once we drop to
        # chunk_ids the ranking is gone.
        provenance = {
            str(result.chunk.id): (rank, result.score)
            for rank, result in enumerate(results, start=1)
        }
        user_content = f"{context}\n\nQuestion: {question}" if results else f"Question: {question}"

        start = time.monotonic()
        with _tracer.start_as_current_span("rag.llm_call") as llm_span:
            llm_span.set_attribute(gen_ai.GEN_AI_PROVIDER_NAME, settings.LLM_PROVIDER)
            llm_span.set_attribute(gen_ai.GEN_AI_REQUEST_MODEL, settings.LLM_MODEL)
            result = get_llm_provider().stream_tool(
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_content}],
                tool=ANSWER_TOOL,
            )
            llm_span.set_attribute(gen_ai.GEN_AI_USAGE_INPUT_TOKENS, result.input_tokens)
            llm_span.set_attribute(gen_ai.GEN_AI_USAGE_OUTPUT_TOKENS, result.output_tokens)
            cost = _estimate_cost(result.input_tokens, result.output_tokens)
            # Not a gen_ai.* attribute: cost-per-token isn't part of the
            # stable semantic conventions yet (checked — only usage/token
            # counts are), so this stays a plain namespaced attribute
            # rather than guessing at a standard that doesn't exist.
            if cost is not None:
                llm_span.set_attribute("lorebase.cost_usd", float(cost))
        latency_ms = int((time.monotonic() - start) * 1000)

        answer_text = str(result.output.get("answer", ""))
        claimed_chunk_ids = result.output.get("cited_chunk_ids", [])
        # The one place finding 7 actually gets enforced: only chunk_ids that
        # were genuinely part of the context we just sent survive. Anything
        # else — a typo'd id, a chunk cited from an earlier turn, a plausible
        # guess — is silently dropped, never persisted as a Citation.
        validated_chunk_ids = [
            chunk_id for chunk_id in claimed_chunk_ids if chunk_id in chunks_by_id
        ]
        # Sorted by retrieval position rather than by the order the model
        # happened to list them: the numbering a reader sees should mean
        # "how the retriever ranked this", which is a fact, not "the order the
        # model mentioned it", which is arbitrary.
        validated_chunk_ids.sort(key=lambda chunk_id: provenance[chunk_id][0])

        with transaction.atomic():
            message = Message.objects.create(
                conversation=conversation,
                role=Message.Role.ASSISTANT,
                content=answer_text,
                latency_ms=latency_ms,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                cost=cost,
                retrieved_count=len(results),
            )
            Citation.objects.bulk_create(
                Citation(
                    message=message,
                    chunk=chunks_by_id[chunk_id],
                    rank=provenance[chunk_id][0],
                    score=provenance[chunk_id][1],
                )
                for chunk_id in validated_chunk_ids
            )
        turn_span.set_attribute("lorebase.retrieved_count", len(results))
        turn_span.set_attribute("lorebase.citations_count", len(validated_chunk_ids))
        return message, results


TITLE_MAX_LENGTH = 60


def _set_title_if_first_message(conversation: Conversation, question: str) -> None:
    """Names a conversation after the question that started it, so a
    history list has something to show. Derived from the question rather
    than generated by an LLM: an extra call per conversation isn't worth
    it for a label, and the first question is usually a good summary of
    what the conversation is about anyway.

    Runs before the user Message is created, so "no messages yet" is a
    reliable test for "this is the first turn".
    """
    if conversation.title or conversation.messages.exists():
        return
    title = " ".join(question.split())
    if len(title) > TITLE_MAX_LENGTH:
        title = title[: TITLE_MAX_LENGTH - 1].rstrip() + "…"
    conversation.title = title
    conversation.save(update_fields=["title"])


def _estimate_cost(input_tokens: int, output_tokens: int) -> Decimal | None:
    input_rate = settings.LLM_COST_PER_MILLION_INPUT_TOKENS_USD
    output_rate = settings.LLM_COST_PER_MILLION_OUTPUT_TOKENS_USD
    if not input_rate and not output_rate:
        return None
    cost = input_tokens * Decimal(str(input_rate)) + output_tokens * Decimal(str(output_rate))
    return cost / Decimal("1_000_000")
