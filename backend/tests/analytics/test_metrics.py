from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from analytics.factories import FeedbackFactory
from analytics.metrics import get_dashboard_metrics
from analytics.models import Feedback
from core.factories import WorkspaceFactory
from ingestion.factories import ChunkFactory
from rag.factories import ConversationFactory, MessageFactory
from rag.models import Citation, Message
from sources.factories import DocumentFactory

pytestmark = pytest.mark.django_db


def _set_created_at(message: Message, when) -> None:
    # auto_now_add ignores whatever `created_at` a caller passes to
    # .create() — it always stamps "now". Bypassing that requires a
    # queryset .update(), which writes the column directly and skips the
    # auto_now_add logic entirely (that logic only fires from .save()).
    Message.objects.filter(pk=message.pk).update(created_at=when)


def test_documents_counts_only_non_deleted_documents_in_the_workspace() -> None:
    workspace = WorkspaceFactory()
    DocumentFactory(source__workspace=workspace)
    DocumentFactory(source__workspace=workspace, deleted=True)
    DocumentFactory()  # different workspace, must not count

    metrics = get_dashboard_metrics([workspace.id])

    assert metrics.documents == 1


def test_queries_by_day_is_zero_filled_and_scoped_to_the_workspace() -> None:
    workspace = WorkspaceFactory()
    conversation = ConversationFactory(workspace=workspace)
    today = timezone.localdate()

    today_message = MessageFactory(conversation=conversation, role=Message.Role.USER)
    _set_created_at(today_message, timezone.now())

    three_days_ago = MessageFactory(conversation=conversation, role=Message.Role.USER)
    _set_created_at(three_days_ago, timezone.now() - timedelta(days=3))

    other_workspace_message = MessageFactory(role=Message.Role.USER)
    _set_created_at(other_workspace_message, timezone.now())

    metrics = get_dashboard_metrics([workspace.id])

    by_date = {day.date: day.count for day in metrics.queries_by_day}
    assert by_date[today] == 1
    assert by_date[today - timedelta(days=3)] == 1
    # A day with no queries is present, at 0, not just absent.
    assert by_date[today - timedelta(days=1)] == 0
    assert metrics.queries_today == 1


def test_assistant_messages_do_not_count_as_queries() -> None:
    workspace = WorkspaceFactory()
    MessageFactory(conversation__workspace=workspace, role=Message.Role.ASSISTANT)

    metrics = get_dashboard_metrics([workspace.id])

    assert metrics.queries_today == 0


def test_cost_this_month_sums_only_this_calendar_month() -> None:
    workspace = WorkspaceFactory()
    conversation = ConversationFactory(workspace=workspace)

    this_month = MessageFactory(
        conversation=conversation, role=Message.Role.ASSISTANT, cost=Decimal("0.05")
    )
    _set_created_at(this_month, timezone.now())

    last_month = MessageFactory(
        conversation=conversation, role=Message.Role.ASSISTANT, cost=Decimal("1.00")
    )
    _set_created_at(last_month, timezone.now() - timedelta(days=40))

    metrics = get_dashboard_metrics([workspace.id])

    assert metrics.cost_this_month_usd == pytest.approx(0.05)


def test_cost_is_none_when_nothing_has_a_recorded_cost() -> None:
    workspace = WorkspaceFactory()
    MessageFactory(conversation__workspace=workspace, role=Message.Role.ASSISTANT, cost=None)

    metrics = get_dashboard_metrics([workspace.id])

    assert metrics.cost_this_month_usd is None


def test_latency_percentiles_are_none_with_no_data() -> None:
    workspace = WorkspaceFactory()

    metrics = get_dashboard_metrics([workspace.id])

    assert metrics.latency_p50_ms is None
    assert metrics.latency_p95_ms is None


def test_latency_percentiles_over_a_known_distribution() -> None:
    """100 latencies, evenly spaced 10..1000ms: p50 should land near the
    middle of the range and p95 well above it — this isn't checking an
    exact value (statistics.quantiles' interpolation method is an
    implementation detail), just that the two percentiles are sane
    relative to each other and to the data.
    """
    workspace = WorkspaceFactory()
    conversation = ConversationFactory(workspace=workspace)
    for i in range(1, 101):
        MessageFactory(conversation=conversation, role=Message.Role.ASSISTANT, latency_ms=i * 10)

    metrics = get_dashboard_metrics([workspace.id])

    assert metrics.latency_p50_ms is not None
    assert metrics.latency_p95_ms is not None
    assert 400 < metrics.latency_p50_ms < 600
    assert metrics.latency_p95_ms > metrics.latency_p50_ms
    assert 900 < metrics.latency_p95_ms <= 1000


def test_positive_feedback_percent_is_none_with_no_feedback() -> None:
    workspace = WorkspaceFactory()

    metrics = get_dashboard_metrics([workspace.id])

    assert metrics.positive_feedback_percent is None
    assert metrics.total_feedback == 0


def test_positive_feedback_percent_is_computed_correctly() -> None:
    workspace = WorkspaceFactory()
    conversation = ConversationFactory(workspace=workspace)
    FeedbackFactory(message__conversation=conversation, rating=Feedback.Rating.UP)
    FeedbackFactory(message__conversation=conversation, rating=Feedback.Rating.UP)
    FeedbackFactory(message__conversation=conversation, rating=Feedback.Rating.DOWN)
    FeedbackFactory()  # different workspace, must not count

    metrics = get_dashboard_metrics([workspace.id])

    assert metrics.total_feedback == 3
    assert metrics.positive_feedback_percent == pytest.approx(66.7, abs=0.1)


def test_never_retrieved_documents_excludes_documents_with_a_cited_chunk() -> None:
    workspace = WorkspaceFactory()
    cited_document = DocumentFactory(source__workspace=workspace)
    cited_chunk = ChunkFactory(document=cited_document)
    message = MessageFactory(conversation__workspace=workspace, role=Message.Role.ASSISTANT)
    Citation.objects.create(message=message, chunk=cited_chunk)

    uncited_document = DocumentFactory(source__workspace=workspace)
    ChunkFactory(document=uncited_document)

    metrics = get_dashboard_metrics([workspace.id])

    assert metrics.documents == 2
    assert metrics.never_retrieved_documents == 1


def test_never_retrieved_documents_is_zero_when_every_chunk_was_cited() -> None:
    workspace = WorkspaceFactory()
    document = DocumentFactory(source__workspace=workspace)
    chunk = ChunkFactory(document=document)
    message = MessageFactory(conversation__workspace=workspace, role=Message.Role.ASSISTANT)
    Citation.objects.create(message=message, chunk=chunk)

    metrics = get_dashboard_metrics([workspace.id])

    assert metrics.never_retrieved_documents == 0
