import pytest

from rag.embeddings.factory import get_embedding_provider
from rag.embeddings.fake import FakeEmbeddingProvider


@pytest.fixture(autouse=True)
def _clear_provider_cache():
    # get_embedding_provider() is memoized (module-global lru_cache), so a
    # cached instance from one test would leak into the next otherwise.
    get_embedding_provider.cache_clear()
    yield
    get_embedding_provider.cache_clear()


def test_fake_provider_selected_by_settings(settings) -> None:
    settings.EMBEDDING_PROVIDER = "fake"
    settings.EMBEDDING_DIMENSIONS = 8

    provider = get_embedding_provider()

    assert isinstance(provider, FakeEmbeddingProvider)
    assert provider.dimensions == 8


def test_unknown_provider_raises(settings) -> None:
    settings.EMBEDDING_PROVIDER = "something-else"

    with pytest.raises(ValueError, match="something-else"):
        get_embedding_provider()
