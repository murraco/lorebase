import json
from typing import cast

from django.contrib.auth.decorators import login_required
from django.http import (
    HttpRequest,
    HttpResponseBadRequest,
    HttpResponseBase,
    JsonResponse,
)
from django.views.decorators.http import require_POST

from core.models import User
from rag.chat.streaming import stream_chat_response
from rag.models import Conversation


@login_required
@require_POST
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

    return stream_chat_response(conversation, question)
