import time

from django.conf import settings
from django.db import transaction
from opentelemetry import trace
from opentelemetry.semconv._incubating.attributes import gen_ai_attributes as gen_ai

from rag.chat.prompting import ANSWER_TOOL, build_context
from rag.chat.service import _estimate_cost, _set_title_if_first_message
from rag.llm.base import ToolSpec
from rag.llm.factory import get_llm_provider
from rag.models import Citation, Conversation, Message
from rag.retrieval.base import RetrievalResult
from rag.retrieval.factory import get_retriever

_tracer = trace.get_tracer("lorebase.chat")

# An LLM round trip that hasn't produced an answer after this many turns is
# stuck (looping, or the corpus genuinely doesn't have the answer), not
# thorough -- it gets forced to answer with whatever it's gathered so far
# rather than looping indefinitely at real API cost.
_MAX_ITERATIONS = 5

SEARCH_TOOL = ToolSpec(
    name="search_knowledge",
    description=(
        "Search the user's notes for information relevant to a query. Can be "
        "called more than once with a different query if the first search "
        "doesn't find what's needed -- e.g. to look up a related term, or "
        "a follow-up detail the first results pointed at but didn't contain."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "What to search for. Doesn't have to repeat the user's question verbatim."
                ),
            }
        },
        "required": ["query"],
    },
)

AGENTIC_SYSTEM_PROMPT = (
    "You answer questions using the user's personal notes. You have a "
    "search_knowledge tool to look up relevant notes, and a provide_answer "
    "tool to give your final answer. Always search before answering -- "
    "never answer from general knowledge. You may call search_knowledge "
    "more than once, with a different query each time, if the first search "
    "doesn't find what you need -- for example a multi-part question may "
    "need more than one search. Every claim in your final answer must be "
    "grounded in notes you actually retrieved, and provide_answer's "
    "cited_chunk_ids must only ever list note IDs you were actually shown. "
    "If, after searching, the notes don't contain the answer, say so "
    "honestly instead of guessing."
)


def ask_agentic(conversation: Conversation, question: str) -> tuple[Message, list[RetrievalResult]]:
    """Same contract as rag.chat.service.ask_with_contexts (persists a
    Message, returns it with what was retrieved) but retrieval is a tool
    the model itself decides whether and how many times to call, instead
    of a fixed pre-fetch step -- see docs/learning-notes.md ("Retrieval
    directo vs. agéntico") for why this exists and how to compare it
    against the direct pipeline. No query rewriting here: an agent that
    can already reformulate its own search query on a second call has no
    separate need for it on the first.
    """
    with _tracer.start_as_current_span("rag.ask_agentic") as turn_span:
        turn_span.set_attribute("lorebase.conversation_id", str(conversation.id))

        _set_title_if_first_message(conversation, question)
        Message.objects.create(conversation=conversation, role=Message.Role.USER, content=question)

        retriever = get_retriever()
        all_results: list[RetrievalResult] = []
        chunks_by_id: dict[str, object] = {}
        provenance: dict[str, tuple[int, float]] = {}
        seen_chunk_ids: set[str] = set()
        search_count = 0
        total_input_tokens = 0
        total_output_tokens = 0
        messages: list[object] = [{"role": "user", "content": question}]

        start = time.monotonic()
        answer_output: dict[str, object] | None = None
        for _iteration in range(_MAX_ITERATIONS):
            with _tracer.start_as_current_span("rag.agent_step") as step_span:
                step_span.set_attribute(gen_ai.GEN_AI_PROVIDER_NAME, settings.LLM_PROVIDER)
                step_span.set_attribute(gen_ai.GEN_AI_REQUEST_MODEL, settings.LLM_MODEL)
                step = get_llm_provider().stream_tools(
                    system=AGENTIC_SYSTEM_PROMPT,
                    messages=messages,
                    tools=[SEARCH_TOOL, ANSWER_TOOL],
                )
                step_span.set_attribute("lorebase.tool_name", step.tool_name)
                step_span.set_attribute(gen_ai.GEN_AI_USAGE_INPUT_TOKENS, step.input_tokens)
                step_span.set_attribute(gen_ai.GEN_AI_USAGE_OUTPUT_TOKENS, step.output_tokens)
            total_input_tokens += step.input_tokens
            total_output_tokens += step.output_tokens
            messages.append({"role": "assistant", "content": step.raw_assistant_content})

            if step.tool_name == ANSWER_TOOL.name:
                answer_output = step.tool_input
                break

            search_count += 1
            query = str(step.tool_input.get("query", question))
            # No span of its own here, same reasoning as the direct path:
            # get_retriever() returns a chain already decorated with
            # @traced_search (rag/retrieval/tracing.py), so this call
            # already produces its own nested span tree.
            results = retriever.search(query, workspace_id=conversation.workspace_id, top_k=5)
            for result in results:
                chunk_id = str(result.chunk.id)
                if chunk_id not in seen_chunk_ids:
                    seen_chunk_ids.add(chunk_id)
                    all_results.append(result)
                    chunks_by_id[chunk_id] = result.chunk
                    provenance[chunk_id] = (len(all_results), result.score)
            messages.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": step.tool_use_id,
                            "content": build_context(results) if results else "No results found.",
                        }
                    ],
                }
            )

        if answer_output is None:
            # _MAX_ITERATIONS exhausted without the model choosing to answer
            # -- one last call, forcing provide_answer (stream_tool's usual
            # contract), so the turn still ends in a valid structured answer
            # instead of silently returning nothing.
            with _tracer.start_as_current_span("rag.agent_step") as step_span:
                step_span.set_attribute("lorebase.tool_name", "forced:" + ANSWER_TOOL.name)
                forced = get_llm_provider().stream_tool(
                    system=AGENTIC_SYSTEM_PROMPT, messages=messages, tool=ANSWER_TOOL
                )
                step_span.set_attribute(gen_ai.GEN_AI_USAGE_INPUT_TOKENS, forced.input_tokens)
                step_span.set_attribute(gen_ai.GEN_AI_USAGE_OUTPUT_TOKENS, forced.output_tokens)
            total_input_tokens += forced.input_tokens
            total_output_tokens += forced.output_tokens
            answer_output = forced.output

        cost = _estimate_cost(total_input_tokens, total_output_tokens)
        latency_ms = int((time.monotonic() - start) * 1000)

        answer_text = str(answer_output.get("answer", ""))
        claimed_chunk_ids = answer_output.get("cited_chunk_ids", [])
        validated_chunk_ids = [
            chunk_id for chunk_id in claimed_chunk_ids if chunk_id in chunks_by_id
        ]
        validated_chunk_ids.sort(key=lambda chunk_id: provenance[chunk_id][0])

        with transaction.atomic():
            message = Message.objects.create(
                conversation=conversation,
                role=Message.Role.ASSISTANT,
                content=answer_text,
                latency_ms=latency_ms,
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
                cost=cost,
                retrieved_count=len(all_results),
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
        turn_span.set_attribute("lorebase.retrieved_count", len(all_results))
        turn_span.set_attribute("lorebase.citations_count", len(validated_chunk_ids))
        turn_span.set_attribute("lorebase.search_count", search_count)
        return message, all_results
