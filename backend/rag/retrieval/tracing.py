"""A single decorator, applied to every concrete Retriever.search(), gives
the whole retrieval pipeline its trace for free. Retrievers wrap each
other — DateAwareRetriever -> RerankingRetriever -> HybridRetriever ->
LexicalRetriever/DenseRetriever — and each layer calls the next through
this same method, so decorating every concrete class produces correctly
nested spans without any of them needing to know the chain exists.
"""

from collections.abc import Callable
from functools import wraps
from typing import TYPE_CHECKING, Any

from opentelemetry import trace

if TYPE_CHECKING:
    from rag.retrieval.base import RetrievalResult, Retriever

_tracer = trace.get_tracer("lorebase.retrieval")

# Callable[..., ...] rather than ParamSpec/Concatenate: getting the fully
# precise generic signature to type-check requires every concrete
# search() to declare `self`/`query` positional-only, which would change
# each retriever's public signature just to satisfy this decorator. Not
# worth it for a wrapper that never touches the arguments it forwards.
_Search = Callable[..., list["RetrievalResult"]]


def traced_search(func: _Search) -> _Search:
    @wraps(func)
    def wrapper(
        self: "Retriever", query: str, *args: Any, **kwargs: Any
    ) -> list["RetrievalResult"]:
        with _tracer.start_as_current_span(f"retrieval.{type(self).__name__}") as span:
            span.set_attribute("retrieval.query", query)
            results = func(self, query, *args, **kwargs)
            span.set_attribute("retrieval.results_count", len(results))
            return results

    return wrapper
