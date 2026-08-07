import pytest

from rag.llm.factory import get_llm_provider
from rag.llm.fake import FakeLLMProvider


@pytest.fixture(autouse=True)
def _clear_cache():
    get_llm_provider.cache_clear()
    yield
    get_llm_provider.cache_clear()


def test_fake_provider_selected_by_settings(settings) -> None:
    settings.LLM_PROVIDER = "fake"

    assert isinstance(get_llm_provider(), FakeLLMProvider)


def test_unknown_provider_raises(settings) -> None:
    settings.LLM_PROVIDER = "something-else"

    with pytest.raises(ValueError, match="something-else"):
        get_llm_provider()
