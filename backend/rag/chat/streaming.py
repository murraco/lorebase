import json
from collections.abc import Generator

from django.http import StreamingHttpResponse

from rag.chat.service import ask
from rag.models import Conversation, Message


def stream_chat_response(conversation: Conversation, question: str) -> StreamingHttpResponse:
    """A plain synchronous view, not the async one the plan originally
    called for: every layer underneath (retrievers, the Django ORM, the
    Voyage/Anthropic SDKs) is synchronous, so wrapping this in `async def`
    would mean sync_to_async-wrapping every blocking call for no real
    concurrency gain — genuine async would need an async-native data layer
    throughout, out of scope here.

    The message is persisted (inside ask()) *before* streaming starts, not
    "when the stream closes" as originally planned: citations can't be
    validated until the full tool call resolves, so there is nothing safe
    to show the client — text or citations — before that point anyway.
    What streams out afterward is already-known-good content, paced for a
    typing effect rather than held back for validation reasons.
    """
    message = ask(conversation, question)

    def event_stream() -> Generator[str]:
        for word in message.content.split(" "):
            yield _sse_event({"delta": word + " "})
        yield _sse_event(
            {
                "done": True,
                "message_id": str(message.id),
                # The provenance header renders straight from the stream,
                # so it must arrive with the answer rather than requiring
                # a follow-up fetch of the message that was just written.
                "latency_ms": message.latency_ms,
                "input_tokens": message.input_tokens,
                "output_tokens": message.output_tokens,
                "cost": float(message.cost) if message.cost is not None else None,
                "retrieved_count": message.retrieved_count,
                "citations": _serialize_citations(message),
            }
        )

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


def _serialize_citations(message: Message) -> list[dict[str, object]]:
    """Must produce the same shape as CitationSerializer: the client types
    both against one generated `Citation`, so a field that exists on only
    one path is a lie the type checker can't catch.

    This emitted `chunk_id` and no `id` for a long time, which meant every
    streamed citation arrived with `id: undefined`. Harmless while answers
    cited a single chunk; the moment one cited several, the UI's
    `track citation.id` saw duplicate keys and rendered no citations at
    all. See the test that compares both field sets.
    """
    return [
        {
            "id": str(citation.id),
            "chunk": str(citation.chunk_id),
            "path": citation.chunk.document.path,
            "heading_path": citation.chunk.heading_path,
            "source_name": citation.chunk.document.source.name,
            "rank": citation.rank,
            "score": citation.score,
            "start_line": citation.chunk.start_line,
            "end_line": citation.chunk.end_line,
            "content": citation.chunk.content,
        }
        for citation in message.citations.select_related("chunk__document__source")
    ]


def _sse_event(payload: dict[str, object]) -> str:
    return f"data: {json.dumps(payload)}\n\n"
