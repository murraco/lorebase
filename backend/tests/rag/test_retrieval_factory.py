import pytest

from core.factories import WorkspaceFactory
from ingestion.factories import ChunkFactory
from ingestion.models import Chunk
from rag.retrieval.base import RetrievalFilters
from rag.retrieval.date_matching import DateAwareRetriever
from rag.retrieval.dense import DenseRetriever
from rag.retrieval.factory import get_retriever
from rag.retrieval.filtering import apply_filters
from rag.retrieval.hybrid import HybridRetriever
from rag.retrieval.lexical import LexicalRetriever
from rag.retrieval.reranking import RerankingRetriever
from sources.factories import DocumentFactory

pytestmark = pytest.mark.django_db


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


def test_disabled_sources_are_excluded_even_without_filters() -> None:
    """The invariant: passing no filters must not mean "search
    everything". A caller that omits filters is not asking to search
    sources the user switched off.
    """
    workspace = WorkspaceFactory()
    enabled = DocumentFactory(source__workspace=workspace, source__enabled=True)
    disabled = DocumentFactory(source__workspace=workspace, source__enabled=False)
    ChunkFactory(document=enabled, content="findable")
    ChunkFactory(document=disabled, content="findable")

    remaining = apply_filters(Chunk.objects.all(), None)

    assert remaining.count() == 1
    assert remaining.get().document_id == enabled.id


def test_disabled_sources_are_excluded_alongside_other_filters() -> None:
    workspace = WorkspaceFactory()
    disabled = DocumentFactory(source__workspace=workspace, source__enabled=False)
    ChunkFactory(document=disabled)

    remaining = apply_filters(
        Chunk.objects.all(), RetrievalFilters(source_ids=[disabled.source_id])
    )

    assert remaining.count() == 0
