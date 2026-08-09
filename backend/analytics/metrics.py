"""Usage and quality metrics — how much this costs and whether the
answers are any good, as distinct from core.status's "is everything wired
up correctly". Both are dashboards; they answer different questions.
"""

import statistics
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any
from uuid import UUID

from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from analytics.models import Feedback
from rag.models import Message
from sources.models import Document

_QUERY_HISTORY_DAYS = 14


@dataclass
class DailyQueryCount:
    date: date
    count: int


@dataclass
class DashboardMetrics:
    documents: int
    queries_today: int
    # Last _QUERY_HISTORY_DAYS days, oldest first, zero-filled for days
    # with no queries — a chart can plot this directly without having to
    # know which dates are missing.
    queries_by_day: list[DailyQueryCount]
    cost_this_month_usd: float | None
    latency_p50_ms: int | None
    latency_p95_ms: int | None
    # None, not 0.0, when nobody has rated anything yet — "no data" and
    # "100% negative" must not look the same on screen.
    positive_feedback_percent: float | None
    total_feedback: int
    never_retrieved_documents: int


def _queries_by_day(workspace_ids: list[UUID], today: date) -> list[DailyQueryCount]:
    start = today - timedelta(days=_QUERY_HISTORY_DAYS - 1)
    counts_by_date = dict(
        Message.objects.filter(
            role=Message.Role.USER,
            conversation__workspace_id__in=workspace_ids,
            created_at__date__gte=start,
        )
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(count=Count("id"))
        .values_list("day", "count")
    )
    return [
        DailyQueryCount(date=day, count=counts_by_date.get(day, 0))
        for day in (start + timedelta(days=i) for i in range(_QUERY_HISTORY_DAYS))
    ]


def _latency_percentiles(workspace_ids: list[UUID]) -> tuple[int | None, int | None]:
    # Pulled into Python rather than computed in Postgres: percentile_cont
    # is standard SQL, but Django has no ORM aggregate for it (checked —
    # not even in django.contrib.postgres.aggregates). Raw SQL would work,
    # but at this app's message volume (personal use, not a query engine)
    # fetching every latency and using the standard library is simpler and
    # exactly as correct, with nothing raw-SQL to keep in sync with the
    # ORM if the query above it ever changes.
    # The .filter(latency_ms__isnull=False) above is real — Postgres
    # drops the NULLs — but django-stubs types the column, not the query,
    # so it still sees `int | None` here. This comprehension is also a
    # runtime no-op and exists so mypy can narrow it to `int`.
    latencies: list[int] = [
        latency
        for latency in Message.objects.filter(
            role=Message.Role.ASSISTANT,
            conversation__workspace_id__in=workspace_ids,
            latency_ms__isnull=False,
        ).values_list("latency_ms", flat=True)
        if latency is not None
    ]
    if not latencies:
        return None, None
    if len(latencies) == 1:
        return latencies[0], latencies[0]
    # n=100 buckets -> quantiles()[49] is p50, [94] is p95.
    percentiles = statistics.quantiles(latencies, n=100, method="inclusive")
    return round(percentiles[49]), round(percentiles[94])


def _positive_feedback_percent(workspace_ids: list[UUID]) -> tuple[float | None, int]:
    feedback = Feedback.objects.filter(message__conversation__workspace_id__in=workspace_ids)
    total = feedback.count()
    if total == 0:
        return None, 0
    positive = feedback.filter(rating=Feedback.Rating.UP).count()
    return round(100 * positive / total, 1), total


def _never_retrieved_documents(workspace_ids: list[UUID]) -> int:
    # "Not seen with a citation on any chunk" rather than "citation count
    # == 0" — this reads as one filter instead of an annotate+count, and
    # it's the same set: a document is excluded the moment any one of its
    # chunks has ever been cited.
    return (
        Document.objects.filter(source__workspace_id__in=workspace_ids, deleted=False)
        .exclude(chunks__citations__isnull=False)
        .distinct()
        .count()
    )


def get_dashboard_metrics(workspace_ids: list[UUID]) -> DashboardMetrics:
    today = timezone.localdate()
    queries_by_day = _queries_by_day(workspace_ids, today)
    latency_p50, latency_p95 = _latency_percentiles(workspace_ids)
    positive_percent, total_feedback = _positive_feedback_percent(workspace_ids)

    month_start = today.replace(day=1)
    cost: dict[str, Any] = Message.objects.filter(
        role=Message.Role.ASSISTANT,
        conversation__workspace_id__in=workspace_ids,
        created_at__date__gte=month_start,
    ).aggregate(total=Sum("cost"))

    return DashboardMetrics(
        documents=Document.objects.filter(
            source__workspace_id__in=workspace_ids, deleted=False
        ).count(),
        queries_today=queries_by_day[-1].count,
        queries_by_day=queries_by_day,
        cost_this_month_usd=float(cost["total"]) if cost["total"] is not None else None,
        latency_p50_ms=latency_p50,
        latency_p95_ms=latency_p95,
        positive_feedback_percent=positive_percent,
        total_feedback=total_feedback,
        never_retrieved_documents=_never_retrieved_documents(workspace_ids),
    )
