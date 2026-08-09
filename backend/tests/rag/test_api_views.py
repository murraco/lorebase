import json
from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

from core.factories import MembershipFactory, WorkspaceFactory
from ingestion.factories import ChunkFactory
from rag.factories import ConversationFactory
from rag.llm.base import LLMProviderUnavailableError, ToolCallResult
from rag.llm.factory import get_llm_provider
from rag.models import Citation, Conversation, Message
from rag.retrieval.base import RetrievalResult
from sources.factories import DocumentFactory

pytestmark = pytest.mark.django_db


def _authed_client(user) -> APIClient:
    # force_login (not force_authenticate): the chat endpoint is a plain
    # Django view guarded by @login_required, not a DRF APIView, so it
    # needs a real session rather than DRF's request-level auth override.
    client = APIClient()
    client.force_login(user)
    return client


@pytest.fixture(autouse=True)
def _clear_llm_cache():
    get_llm_provider.cache_clear()
    yield
    get_llm_provider.cache_clear()


class _StubRetriever:
    def __init__(self, results):
        self._results = results

    def search(self, query, *, workspace_id, top_k=10, filters=None):
        return self._results


def test_list_conversations_returns_only_own_workspace() -> None:
    membership = MembershipFactory()
    own_conversation = ConversationFactory(workspace=membership.workspace, user=membership.user)
    ConversationFactory()  # different workspace, must not appear

    response = _authed_client(membership.user).get("/api/conversations/")

    assert response.status_code == 200
    ids = [item["id"] for item in response.json()["results"]]
    assert ids == [str(own_conversation.id)]


def test_cannot_retrieve_conversation_from_another_workspace() -> None:
    membership = MembershipFactory()
    other_conversation = ConversationFactory()

    response = _authed_client(membership.user).get(f"/api/conversations/{other_conversation.id}/")

    assert response.status_code == 404


def test_create_conversation_rejects_a_workspace_the_user_is_not_a_member_of() -> None:
    membership = MembershipFactory()
    other_workspace = WorkspaceFactory()

    response = _authed_client(membership.user).post(
        "/api/conversations/", {"workspace": str(other_workspace.id)}, format="json"
    )

    assert response.status_code == 400


def test_create_conversation_sets_user_from_the_request_not_the_payload() -> None:
    membership = MembershipFactory()
    other_user = MembershipFactory(workspace=membership.workspace).user

    response = _authed_client(membership.user).post(
        "/api/conversations/",
        {"workspace": str(membership.workspace.id), "user": str(other_user.id)},
        format="json",
    )

    assert response.status_code == 201
    conversation = Conversation.objects.get(pk=response.json()["id"])
    assert conversation.user_id == membership.user.id


def test_messages_are_scoped_to_the_users_workspace_and_read_only() -> None:
    membership = MembershipFactory()
    own_conversation = ConversationFactory(workspace=membership.workspace, user=membership.user)
    own_message = Message.objects.create(
        conversation=own_conversation, role=Message.Role.USER, content="hi"
    )
    other_conversation = ConversationFactory()
    Message.objects.create(conversation=other_conversation, role=Message.Role.USER, content="hi")

    response = _authed_client(membership.user).get("/api/messages/")

    assert response.status_code == 200
    ids = [item["id"] for item in response.json()["results"]]
    assert ids == [str(own_message.id)]

    response = _authed_client(membership.user).post("/api/messages/", {}, format="json")
    assert response.status_code == 405


def test_chat_stream_persists_and_returns_a_validated_citation() -> None:
    membership = MembershipFactory()
    conversation = ConversationFactory(workspace=membership.workspace, user=membership.user)
    document = DocumentFactory(source__workspace=membership.workspace)
    chunk = ChunkFactory(document=document, content="content", start_line=3, end_line=7)

    fake_llm = get_llm_provider()
    fake_llm.next_tool_result = ToolCallResult(
        output={"answer": "the answer", "cited_chunk_ids": [str(chunk.id)]},
        input_tokens=10,
        output_tokens=5,
    )

    with patch(
        "rag.chat.service.get_retriever",
        return_value=_StubRetriever([RetrievalResult(chunk=chunk, score=1.0)]),
    ):
        response = _authed_client(membership.user).post(
            f"/api/conversations/{conversation.id}/chat/",
            data=json.dumps({"question": "what is it?"}),
            content_type="application/json",
        )
        events = [event.decode() for event in response.streaming_content]

    assert response.status_code == 200
    assert response["Content-Type"] == "text/event-stream"
    done_payload = json.loads(events[-1].removeprefix("data: ").strip())
    assert done_payload["done"] is True
    assert done_payload["citations"][0]["path"] == document.path
    assert conversation.messages.filter(role=Message.Role.ASSISTANT).exists()


def test_chat_stream_on_another_workspaces_conversation_is_not_found() -> None:
    membership = MembershipFactory()
    other_conversation = ConversationFactory()

    response = _authed_client(membership.user).post(
        f"/api/conversations/{other_conversation.id}/chat/",
        data=json.dumps({"question": "what is it?"}),
        content_type="application/json",
    )

    assert response.status_code == 404


def test_chat_stream_requires_authentication() -> None:
    conversation = ConversationFactory()

    response = APIClient().post(
        f"/api/conversations/{conversation.id}/chat/",
        data=json.dumps({"question": "what is it?"}),
        content_type="application/json",
    )

    assert response.status_code in (302, 401, 403)


def test_chat_stream_rejects_a_missing_question_field() -> None:
    membership = MembershipFactory()
    conversation = ConversationFactory(workspace=membership.workspace, user=membership.user)

    response = _authed_client(membership.user).post(
        f"/api/conversations/{conversation.id}/chat/",
        data=json.dumps({}),
        content_type="application/json",
    )

    assert response.status_code == 400


def test_delete_conversation_removes_it_and_its_messages() -> None:
    membership = MembershipFactory()
    conversation = ConversationFactory(workspace=membership.workspace, user=membership.user)
    Message.objects.create(conversation=conversation, role=Message.Role.USER, content="hi")

    response = _authed_client(membership.user).delete(f"/api/conversations/{conversation.id}/")

    assert response.status_code == 204
    assert not Conversation.objects.filter(pk=conversation.id).exists()
    assert not Message.objects.filter(conversation_id=conversation.id).exists()


def test_cannot_delete_a_conversation_from_another_workspace() -> None:
    membership = MembershipFactory()
    other_conversation = ConversationFactory()

    response = _authed_client(membership.user).delete(
        f"/api/conversations/{other_conversation.id}/"
    )

    assert response.status_code == 404
    assert Conversation.objects.filter(pk=other_conversation.id).exists()


def test_deleting_a_conversation_leaves_the_cited_chunks_alone() -> None:
    """Citation points at a Chunk, never the reverse — deleting a
    conversation must not take indexed content with it.
    """
    membership = MembershipFactory()
    conversation = ConversationFactory(workspace=membership.workspace, user=membership.user)
    message = Message.objects.create(
        conversation=conversation, role=Message.Role.ASSISTANT, content="answer"
    )
    chunk = ChunkFactory(document__source__workspace=membership.workspace)
    Citation.objects.create(message=message, chunk=chunk)

    _authed_client(membership.user).delete(f"/api/conversations/{conversation.id}/")

    chunk.refresh_from_db()
    assert chunk.pk is not None


def test_chat_returns_503_when_the_model_is_unavailable() -> None:
    """503, not 500: the request was fine, the dependency was not — and
    that distinction is what tells the client retrying is worthwhile.
    """
    membership = MembershipFactory()
    conversation = ConversationFactory(workspace=membership.workspace, user=membership.user)

    with patch(
        "rag.chat.views.stream_chat_response",
        side_effect=LLMProviderUnavailableError("rate limited"),
    ):
        response = _authed_client(membership.user).post(
            f"/api/conversations/{conversation.id}/chat/",
            json.dumps({"question": "hello"}),
            content_type="application/json",
        )

    assert response.status_code == 503
    assert "try again" in response.json()["detail"].lower()


def test_chat_returns_500_for_an_unexpected_failure() -> None:
    """An unexpected error is a bug, and telling the user to retry would
    send them round a loop that cannot succeed.
    """
    membership = MembershipFactory()
    conversation = ConversationFactory(workspace=membership.workspace, user=membership.user)

    with patch("rag.chat.views.stream_chat_response", side_effect=ValueError("boom")):
        response = _authed_client(membership.user).post(
            f"/api/conversations/{conversation.id}/chat/",
            json.dumps({"question": "hello"}),
            content_type="application/json",
        )

    assert response.status_code == 500
    assert "try again" not in response.json()["detail"].lower()
