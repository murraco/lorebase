import json
import logging
from typing import cast

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import (
    HttpRequest,
    HttpResponseBadRequest,
    HttpResponseBase,
    JsonResponse,
)
from django.views.decorators.http import require_POST

from core.models import User
from core.ratelimit import rate_limit
from rag.chat.streaming import stream_chat_response
from rag.embeddings.base import EmbeddingProviderUnavailableError
from rag.llm.base import LLMProviderUnavailableError
from rag.models import Conversation

logger = logging.getLogger(__name__)


@login_required
@require_POST
@rate_limit(
    scope="chat", limit=settings.CHAT_RATE_LIMIT_PER_MINUTE, window_seconds=60
)
def chat_stream_view(request: HttpRequest, conversation_id: str) -> HttpResponseBase:
    # A single membership-filtered lookup rather than "fetch, then check
    # workspace separately": returning 404 either way (doesn't exist vs.
    # exists in a workspace you're not in) avoids confirming to a caller
    # that a given conversation id belongs to someone else's workspace.
    # login_required guarantees an authenticated user at runtime; the cast
    # just tells mypy what it already knows.
    user = cast(User, request.user)
    try:
        conversation = Conversation.objects.get(
            pk=conversation_id, workspace__memberships__user=user
        )
    except Conversation.DoesNotExist:
        return JsonResponse({"detail": "Not found."}, status=404)

    try:
        body = json.loads(request.body)
        question = body["question"]
    except (json.JSONDecodeError, KeyError):
        return HttpResponseBadRequest("Expected a JSON body with a 'question' field.")

    # ask() runs to completion before the first byte is streamed, so a
    # provider failure surfaces here rather than mid-response. That is
    # what makes a clean status code possible at all: once bytes are on
    # the wire the status is already sent and an error can only be an
    # abrupt truncation.
    try:
        return stream_chat_response(conversation, question)
    except (LLMProviderUnavailableError, EmbeddingProviderUnavailableError) as exc:
        # 503, not 500: the request was fine, the dependency was not, and
        # the distinction is what tells the client retrying is worthwhile.
        logger.warning("Chat turn failed, provider unavailable: %s", exc)
        return JsonResponse(
            {"detail": "The model is unavailable right now. Try again in a moment."},
            status=503,
        )
    except Exception:
        logger.exception("Chat turn failed unexpectedly")
        return JsonResponse(
            {"detail": "Something went wrong answering that."},
            status=500,
        )
