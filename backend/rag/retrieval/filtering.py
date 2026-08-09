from django.db.models import QuerySet

from ingestion.models import Chunk
from rag.retrieval.base import RetrievalFilters


def apply_filters(qs: QuerySet[Chunk], filters: RetrievalFilters | None) -> QuerySet[Chunk]:
    """Shared by every Retriever so lexical/dense/hybrid never drift on
    what a filter actually means.

    The disabled-source exclusion is applied unconditionally, before the
    early return: "a source that is off must never be retrieved" is an
    invariant like workspace scoping, not a caller preference. Putting it
    behind `if filters` would mean any caller that passes None silently
    searches sources the user switched off.
    """
    qs = qs.filter(document__source__enabled=True)
    if filters is None:
        return qs
    if filters.source_ids:
        qs = qs.filter(document__source_id__in=filters.source_ids)
    if filters.updated_after:
        qs = qs.filter(document__updated_at__gte=filters.updated_after)
    return qs
