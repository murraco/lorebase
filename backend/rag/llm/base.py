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


@dataclass
class AgentStepResult:
    """One turn of a tool-use loop: which tool the model picked, its
    input, and enough of the raw response to let the caller continue the
    conversation. `raw_assistant_content` is deliberately untyped further
    than "opaque, provider-specific content blocks" — it only ever gets
    fed back into a later call on the *same* provider (as that turn's
    assistant message), never inspected by the orchestration loop itself.
    `tool_use_id` is what a follow-up tool_result message must reference.
    """

    tool_name: str
    tool_input: dict[str, Any]
    tool_use_id: str
    raw_assistant_content: Any
    input_tokens: int
    output_tokens: int


class LLMProvider(ABC):
    """The plan's original shape was three capabilities (chat, stream,
    tools). In practice we mostly need two: a plain one-shot call for
    small internal steps (query rewriting), and a *streamed, tool-forced*
    call for the actual user-facing answer — streaming and tool-forcing
    aren't independent needs here, they're the same call. See
    AnthropicProvider.stream_tool for how the two combine.

    stream_tools (plural) is the third, added for agentic retrieval
    (Etapa 16 Task 6): stream_tool forces one specific tool, which is
    exactly wrong for letting the model choose between searching again
    and answering. It offers every given tool and returns whichever one
    the model picked — a single turn. The loop itself (executing a
    non-terminal tool, feeding its result back, deciding when to stop)
    is the caller's job, not this interface's: this class knows nothing
    about retrieval, only about talking to one LLM turn at a time.
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

    @abstractmethod
    def stream_tools(
        self, *, system: str, messages: list[Any], tools: list[ToolSpec]
    ) -> AgentStepResult:
        """Offers every tool in `tools` and lets the model pick which one
        to call (some tool must be called, but not a specific one) —
        `messages` accepts richer, provider-native turns than chat/
        stream_tool's plain strings, since a tool-use loop's history
        includes tool_use/tool_result blocks, not just text.
        """
