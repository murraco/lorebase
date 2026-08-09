from uuid import UUID, uuid4

import pytest

from core.factories import WorkspaceFactory
from rag.retrieval.base import RetrievalFilters, RetrievalResult, Retriever
from rag.retrieval.lexical import LexicalRetriever
from rag.retrieval.tracing import traced_search


class _FakeRetriever(Retriever):
    """Doesn't touch the database — this is testing the decorator, not a
    real search implementation."""

    def __init__(self, results: list[RetrievalResult]) -> None:
        self._results = results

    @traced_search
    def search(
        self,
        query: str,
        *,
        workspace_id: UUID,
        top_k: int = 10,
        filters: RetrievalFilters | None = None,
    ) -> list[RetrievalResult]:
        return self._results[:top_k]


class _WrappingFakeRetriever(Retriever):
    """Mirrors the real wrapper shape (DateAwareRetriever etc.): calls an
    inner Retriever's own decorated search()."""

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
        return self._inner.search(query, workspace_id=workspace_id, top_k=top_k, filters=filters)


def test_traced_search_records_a_span_named_after_the_class(otel_spans) -> None:
    retriever = _FakeRetriever([])

    retriever.search("what happened on the 21st", workspace_id=uuid4())

    (span,) = otel_spans.get_finished_spans()
    assert span.name == "retrieval._FakeRetriever"


def test_traced_search_records_query_and_results_count(otel_spans) -> None:
    fake_results = [
        RetrievalResult(chunk=None, score=1.0),  # type: ignore[arg-type]
        RetrievalResult(chunk=None, score=0.5),  # type: ignore[arg-type]
    ]
    retriever = _FakeRetriever(fake_results)

    retriever.search("what happened on the 21st", workspace_id=uuid4())

    (span,) = otel_spans.get_finished_spans()
    assert span.attributes["retrieval.query"] == "what happened on the 21st"
    assert span.attributes["retrieval.results_count"] == 2


def test_wrapped_retrievers_produce_nested_spans(otel_spans) -> None:
    """The actual point of decorating every concrete class: a wrapper
    chain (like DateAwareRetriever -> RerankingRetriever -> ...) produces
    a full parent/child span tree with zero tracing-specific code in any
    of the wrappers themselves."""
    inner = _FakeRetriever([])
    outer = _WrappingFakeRetriever(inner)

    outer.search("query", workspace_id=uuid4())

    spans = otel_spans.get_finished_spans()
    names = {span.name for span in spans}
    assert names == {"retrieval._WrappingFakeRetriever", "retrieval._FakeRetriever"}

    outer_span = next(s for s in spans if s.name == "retrieval._WrappingFakeRetriever")
    inner_span = next(s for s in spans if s.name == "retrieval._FakeRetriever")
    assert inner_span.parent.span_id == outer_span.context.span_id


@pytest.mark.django_db
def test_a_real_retriever_is_actually_decorated(otel_spans) -> None:
    """Not just the fake above — confirms @traced_search is really applied
    to a concrete production retriever, so this regresses if someone ever
    removes the decorator from a class without removing the import."""
    workspace = WorkspaceFactory()

    LexicalRetriever().search("anything", workspace_id=workspace.id)

    (span,) = otel_spans.get_finished_spans()
    assert span.name == "retrieval.LexicalRetriever"
