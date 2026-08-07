from functools import lru_cache

from django.conf import settings

from rag.llm.base import LLMProvider


@lru_cache
def get_llm_provider() -> LLMProvider:
    if settings.LLM_PROVIDER == "anthropic":
        from rag.llm.anthropic import AnthropicProvider

        return AnthropicProvider()
    if settings.LLM_PROVIDER == "fake":
        from rag.llm.fake import FakeLLMProvider

        return FakeLLMProvider()
    raise ValueError(f"Unknown LLM_PROVIDER: {settings.LLM_PROVIDER!r}")
