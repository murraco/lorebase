import pytest
from rest_framework.test import APIClient

from core.factories import MembershipFactory
from ingestion.factories import ChunkFactory
from rag.factories import ConversationFactory
from rag.models import Citation, Message
from sources.factories import DocumentFactory, SourceFactory

pytestmark = pytest.mark.django_db


def _authed_client(user) -> APIClient:
    client = APIClient()
    client.force_login(user)
    return client


def test_reports_the_model_of_the_active_provider_only(settings) -> None:
    """The whole point of the panel: show what's actually in use. With
    EMBEDDING_PROVIDER=local it must report the local model, not the
    Voyage one that's also configured and simply inert.
    """
    settings.EMBEDDING_PROVIDER = "local"
    settings.LOCAL_EMBEDDING_MODEL = "intfloat/multilingual-e5-large"
    settings.EMBEDDING_MODEL = "voyage-4"
    membership = MembershipFactory()

    response = _authed_client(membership.user).get("/api/system/status/")

    assert response.status_code == 200
    assert response.json()["embedding"] == {
        "provider": "local",
        "model": "intfloat/multilingual-e5-large",
    }


def test_switching_provider_switches_the_reported_model(settings) -> None:
    settings.EMBEDDING_PROVIDER = "voyage"
    settings.EMBEDDING_MODEL = "voyage-4"
    membership = MembershipFactory()

    response = _authed_client(membership.user).get("/api/system/status/")

    assert response.json()["embedding"] == {"provider": "voyage", "model": "voyage-4"}


def test_flags_fake_providers(settings) -> None:
    """The regression this panel exists for: EMBEDDING_PROVIDER=fake once
    ran against real data unnoticed, silently filling the index with
    meaningless vectors.
    """
    settings.EMBEDDING_PROVIDER = "fake"
    membership = MembershipFactory()

    response = _authed_client(membership.user).get("/api/system/status/")

    assert response.json()["using_fake_providers"] is True


def test_does_not_flag_real_providers(settings) -> None:
    settings.EMBEDDING_PROVIDER = "local"
    settings.RERANK_PROVIDER = "local"
    settings.LLM_PROVIDER = "anthropic"
    membership = MembershipFactory()

    response = _authed_client(membership.user).get("/api/system/status/")

    assert response.json()["using_fake_providers"] is False


def test_counts_are_scoped_to_the_users_workspaces() -> None:
    membership = MembershipFactory()
    own_source = SourceFactory(workspace=membership.workspace)
    own_document = DocumentFactory(source=own_source)
    ChunkFactory(document=own_document, embedding=[0.0] * 1024)
    ChunkFactory(document=own_document, embedding=None)

    other_document = DocumentFactory()
    ChunkFactory(document=other_document, embedding=[0.0] * 1024)

    response = _authed_client(membership.user).get("/api/system/status/")

    body = response.json()
    assert body["sources"] == 1
    assert body["documents"] == 1
    assert body["chunks"] == 2
    assert body["embedded_chunks"] == 1


def test_deleted_documents_are_not_counted() -> None:
    membership = MembershipFactory()
    source = SourceFactory(workspace=membership.workspace)
    DocumentFactory(source=source, deleted=True)

    response = _authed_client(membership.user).get("/api/system/status/")

    assert response.json()["documents"] == 0


def test_requires_authentication() -> None:
    response = APIClient().get("/api/system/status/")

    assert response.status_code in (401, 403)


def test_answer_metrics_are_not_distorted_by_the_citation_join() -> None:
    """Two answers, one citing three chunks and one citing none.

    Aggregating citations in the same query as the answer count would fan
    the first answer into three rows: the count would read 4 instead of 2,
    and the average latency would be pulled toward the heavily-cited
    answer instead of being a plain mean.
    """
    membership = MembershipFactory()
    conversation = ConversationFactory(workspace=membership.workspace, user=membership.user)
    document = DocumentFactory(source__workspace=membership.workspace)

    cited = Message.objects.create(
        conversation=conversation,
        role=Message.Role.ASSISTANT,
        content="grounded",
        latency_ms=1000,
    )
    for rank in range(1, 4):
        Citation.objects.create(
            message=cited, chunk=ChunkFactory(document=document), rank=rank, score=0.5
        )
    Message.objects.create(
        conversation=conversation,
        role=Message.Role.ASSISTANT,
        content="ungrounded",
        latency_ms=3000,
    )

    body = _authed_client(membership.user).get("/api/system/status/").json()

    assert body["answers"] == 2
    assert body["avg_latency_ms"] == 2000  # plain mean, not weighted by citations
    assert body["avg_citations_per_answer"] == 1.5
    assert body["ungrounded_answers"] == 1


def test_answer_metrics_are_null_when_nothing_has_been_asked() -> None:
    membership = MembershipFactory()

    body = _authed_client(membership.user).get("/api/system/status/").json()

    assert body["answers"] == 0
    assert body["avg_latency_ms"] is None
    assert body["avg_citations_per_answer"] is None
    assert body["ungrounded_answers"] == 0
