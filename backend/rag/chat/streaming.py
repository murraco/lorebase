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
                "citations": _serialize_citations(message),
            }
        )

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


def _serialize_citations(message: Message) -> list[dict[str, object]]:
    return [
        {
            "chunk_id": str(citation.chunk_id),
            "path": citation.chunk.document.path,
            "heading_path": citation.chunk.heading_path,
            "start_line": citation.chunk.start_line,
            "end_line": citation.chunk.end_line,
            "content": citation.chunk.content,
        }
        for citation in message.citations.select_related("chunk__document")
    ]


def _sse_event(payload: dict[str, object]) -> str:
    return f"data: {json.dumps(payload)}\n\n"
