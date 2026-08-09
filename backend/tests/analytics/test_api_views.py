import pytest
from rest_framework.test import APIClient

from analytics.models import Feedback
from core.factories import MembershipFactory
from rag.factories import ConversationFactory, MessageFactory
from rag.models import Message

pytestmark = pytest.mark.django_db


def _authed_client(user) -> APIClient:
    client = APIClient()
    client.force_login(user)
    return client


def test_dashboard_returns_metrics_for_the_caller_s_workspace() -> None:
    membership = MembershipFactory()
    MessageFactory(conversation__workspace=membership.workspace, role=Message.Role.ASSISTANT)

    response = _authed_client(membership.user).get("/api/analytics/dashboard/")

    assert response.status_code == 200
    body = response.json()
    assert "queries_by_day" in body
    assert "never_retrieved_documents" in body


def test_dashboard_requires_authentication() -> None:
    response = APIClient().get("/api/analytics/dashboard/")

    assert response.status_code in (401, 403)


def test_feedback_creates_a_new_rating() -> None:
    membership = MembershipFactory()
    conversation = ConversationFactory(workspace=membership.workspace)
    message = MessageFactory(conversation=conversation, role=Message.Role.ASSISTANT)

    response = _authed_client(membership.user).post(
        f"/api/messages/{message.id}/feedback/", {"rating": "up", "comment": "Nice."}, format="json"
    )

    assert response.status_code == 200
    feedback = Feedback.objects.get(message=message)
    assert feedback.rating == Feedback.Rating.UP
    assert feedback.comment == "Nice."


def test_feedback_updates_instead_of_duplicating() -> None:
    """The whole point of the OneToOneField: giving 👎 after already
    having given 👍 on the same message replaces it, it doesn't error and
    it doesn't leave two rows."""
    membership = MembershipFactory()
    conversation = ConversationFactory(workspace=membership.workspace)
    message = MessageFactory(conversation=conversation, role=Message.Role.ASSISTANT)
    client = _authed_client(membership.user)
    client.post(f"/api/messages/{message.id}/feedback/", {"rating": "up"}, format="json")

    response = client.post(
        f"/api/messages/{message.id}/feedback/", {"rating": "down"}, format="json"
    )

    assert response.status_code == 200
    assert Feedback.objects.filter(message=message).count() == 1
    assert Feedback.objects.get(message=message).rating == Feedback.Rating.DOWN


def test_feedback_rejects_an_invalid_rating() -> None:
    membership = MembershipFactory()
    conversation = ConversationFactory(workspace=membership.workspace)
    message = MessageFactory(conversation=conversation, role=Message.Role.ASSISTANT)

    response = _authed_client(membership.user).post(
        f"/api/messages/{message.id}/feedback/", {"rating": "sideways"}, format="json"
    )

    assert response.status_code == 400
    assert not Feedback.objects.filter(message=message).exists()


def test_feedback_on_a_user_message_is_rejected() -> None:
    """Rating a question, rather than an answer, has no meaning — this
    is the role=ASSISTANT filter in MessageFeedbackView.post()."""
    membership = MembershipFactory()
    conversation = ConversationFactory(workspace=membership.workspace)
    message = MessageFactory(conversation=conversation, role=Message.Role.USER)

    response = _authed_client(membership.user).post(
        f"/api/messages/{message.id}/feedback/", {"rating": "up"}, format="json"
    )

    assert response.status_code == 404


def test_feedback_on_another_workspaces_message_is_not_found() -> None:
    membership = MembershipFactory()
    other_message = MessageFactory(role=Message.Role.ASSISTANT)

    response = _authed_client(membership.user).post(
        f"/api/messages/{other_message.id}/feedback/", {"rating": "up"}, format="json"
    )

    assert response.status_code == 404
    assert not Feedback.objects.filter(message=other_message).exists()
