import pytest

from rag.retrieval.date_matching import DateAwareRetriever
from rag.retrieval.dense import DenseRetriever
from rag.retrieval.factory import get_retriever
from rag.retrieval.hybrid import HybridRetriever
from rag.retrieval.lexical import LexicalRetriever
from rag.retrieval.reranking import RerankingRetriever


@pytest.fixture(autouse=True)
def _clear_retriever_cache():
    get_retriever.cache_clear()
    yield
    get_retriever.cache_clear()


@pytest.mark.parametrize(
    ("strategy", "expected_type"),
    [
        # lexical/dense stay unwrapped on purpose — see factory.py.
        ("lexical", LexicalRetriever),
        ("dense", DenseRetriever),
    ],
)
def test_strategy_selects_the_right_retriever(settings, strategy, expected_type) -> None:
    settings.RETRIEVAL_STRATEGY = strategy

    assert isinstance(get_retriever(), expected_type)


def test_hybrid_is_wrapped_with_date_awareness(settings) -> None:
    settings.RETRIEVAL_STRATEGY = "hybrid"

    retriever = get_retriever()

    assert isinstance(retriever, DateAwareRetriever)
    assert isinstance(retriever._inner, HybridRetriever)  # noqa: SLF001


def test_hybrid_reranked_is_wrapped_with_date_awareness_around_reranking(settings) -> None:
    settings.RETRIEVAL_STRATEGY = "hybrid_reranked"

    retriever = get_retriever()

    assert isinstance(retriever, DateAwareRetriever)
    assert isinstance(retriever._inner, RerankingRetriever)  # noqa: SLF001


def test_unknown_strategy_raises(settings) -> None:
    settings.RETRIEVAL_STRATEGY = "nonsense"

    with pytest.raises(ValueError, match="nonsense"):
        get_retriever()
