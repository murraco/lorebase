import re
from uuid import UUID

from ingestion.models import Chunk
from rag.retrieval.base import RetrievalFilters, RetrievalResult, Retriever
from rag.retrieval.filtering import apply_filters
from rag.retrieval.tracing import traced_search

_ISO_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")

# How many date-matched chunks to force in, at most — a date mentioned in
# passing across many unrelated entries shouldn't crowd out top_k entirely.
_MAX_DATE_MATCHES = 3


class DateAwareRetriever(Retriever):
    """Wraps any Retriever and, when the query contains a recognizable
    ISO date (rag.chat.rewriting.rewrite_query normalizes natural-language
    dates into this form before retrieval ever sees them), also does a
    direct lookup for chunks whose content mentions that date — merged in
    ahead of whatever the wrapped retriever found on its own.

    Exists because neither lexical nor dense search reliably surfaces a
    specific day's entry in a large, uniformly-shaped journal, verified
    against real data: lexical's AND-of-every-term semantics fails
    outright once the query has words the content doesn't share (a
    Spanish question against English content, say — every non-date word
    fails to match, so websearch_to_tsquery matches nothing at all), and
    dense embeddings alone don't strongly differentiate between
    similarly-shaped daily entries. A cross-encoder reranker resolves
    this well when available (it reads query and chunk together, so it
    can directly notice "this chunk literally contains the date asked
    about") — this fixes the same case without depending on it.
    """

    def __init__(self, inner: Retriever) -> None:
        self._inner = inner

    @traced_search
    def search(
        self,
        query: str,
        *,
        workspace_id: UUID,
        top_k: int = 10,
        filters: RetrievalFilters | None = None,
    ) -> list[RetrievalResult]:
        results = self._inner.search(query, workspace_id=workspace_id, top_k=top_k, filters=filters)

        match = _ISO_DATE_RE.search(query)
        if match is None:
            return results

        seen_chunk_ids = {result.chunk.id for result in results}
        qs = Chunk.objects.filter(document__source__workspace_id=workspace_id).filter(
            content__icontains=match.group(0)
        )
        qs = apply_filters(qs, filters).exclude(id__in=seen_chunk_ids).select_related("document")
        # Explicit ordering because the slice below is a LIMIT: neither
        # Chunk.Meta nor BaseModel.Meta defines `ordering`, so without
        # this Postgres is free to return any 3 of the matching rows, and
        # a different query plan can return different ones between runs.
        # File order is both deterministic and the most natural reading
        # order for several chunks of the same day.
        qs = qs.order_by("document__path", "index")

        date_matches = [RetrievalResult(chunk=chunk, score=1.0) for chunk in qs[:_MAX_DATE_MATCHES]]
        if not date_matches:
            return results

        return (date_matches + results)[:top_k]
