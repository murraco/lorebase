from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


class LLMProviderUnavailableError(Exception):
    """The model could not be reached or refused the request for a reason
    that is not the caller's fault: rate limit, timeout, upstream outage.

    Same shape as RerankerUnavailableError and
    EmbeddingProviderUnavailableError — a provider-agnostic type callers
    can catch without importing a vendor SDK. Distinguished from an
    unexpected bug on purpose: one is worth telling the user to retry,
    the other is worth fixing.
    """


@dataclass
class ChatResult:
    text: str
    input_tokens: int
    output_tokens: int


@dataclass
class ToolCallResult:
    output: dict[str, Any]
    input_tokens: int
    output_tokens: int


@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]


class LLMProvider(ABC):
    """The plan's original shape was three capabilities (chat, stream,
    tools). In practice we only ever need two: a plain one-shot call for
    small internal steps (query rewriting), and a *streamed, tool-forced*
    call for the actual user-facing answer — streaming and tool-forcing
    aren't independent needs here, they're the same call. See
    AnthropicProvider.stream_tool for how the two combine.
    """

    @abstractmethod
    def chat(self, *, system: str, messages: list[dict[str, str]]) -> ChatResult:
        """One-shot, plain-text completion. No tools, no streaming."""

    @abstractmethod
    def stream_tool(
        self, *, system: str, messages: list[dict[str, str]], tool: ToolSpec
    ) -> ToolCallResult:
        """Forces a structured response via a single named tool, over the
        provider's real streaming connection. Resolves once the tool call
        is complete — citations can only be checked against a *complete*
        cited_chunk_ids list, so there is nothing valid to relay to an
        actual HTTP client before this returns.
        """
