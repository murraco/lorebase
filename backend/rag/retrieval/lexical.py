from uuid import UUID

from django.contrib.postgres.search import SearchQuery, SearchRank
from django.db.models import F

from ingestion.models import Chunk
from rag.retrieval.base import RetrievalFilters, RetrievalResult, Retriever
from rag.retrieval.filtering import apply_filters
from rag.retrieval.tracing import traced_search


class LexicalRetriever(Retriever):
    """Postgres full-text search over the Chunk.search_vector generated
    column. Catches exact terms, identifiers, and filenames that embeddings
    often blur past. search_type="websearch" maps to Postgres's
    websearch_to_tsquery() — search-engine syntax ("quoted phrases",
    -exclusions, OR) instead of requiring hand-built tsquery syntax, which
    matters because the input here is a natural-language question, not a
    curated search string. cover_density=True selects ts_rank_cd over
    plain ts_rank — it additionally rewards matched terms appearing close
    together, not just present.
    """

    @traced_search
    def search(
        self,
        query: str,
        *,
        workspace_id: UUID,
        top_k: int = 10,
        filters: RetrievalFilters | None = None,
    ) -> list[RetrievalResult]:
        search_query = SearchQuery(query, search_type="websearch", config="english")

        qs = Chunk.objects.filter(document__source__workspace_id=workspace_id)
        qs = apply_filters(qs, filters)
        qs = (
            qs.annotate(rank=SearchRank(F("search_vector"), search_query, cover_density=True))
            .filter(search_vector=search_query)
            .order_by("-rank")[:top_k]
        )
        return [RetrievalResult(chunk=chunk, score=chunk.rank) for chunk in qs]
