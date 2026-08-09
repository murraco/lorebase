from typing import Any

import anthropic
from django.conf import settings

from rag.llm.base import (
    AgentStepResult,
    ChatResult,
    LLMProvider,
    LLMProviderUnavailableError,
    ToolCallResult,
    ToolSpec,
)

# Rate limits, timeouts and upstream failures — everything that is worth
# retrying rather than fixing. InvalidRequestError is deliberately absent:
# a malformed request is a bug here, and hiding it behind "try again"
# would waste the user's time on something that will never succeed.
_UNAVAILABLE = (
    anthropic.RateLimitError,
    anthropic.APITimeoutError,
    anthropic.APIConnectionError,
    anthropic.InternalServerError,
)

_CHAT_MAX_TOKENS = 1024
_TOOL_CALL_MAX_TOKENS = 2048


class AnthropicProvider(LLMProvider):
    def __init__(self) -> None:
        self._client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, max_retries=3)
        self._model = settings.LLM_MODEL

    def chat(self, *, system: str, messages: list[dict[str, str]]) -> ChatResult:
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=_CHAT_MAX_TOKENS,
                system=system,
                messages=messages,  # type: ignore[arg-type]
            )
        except _UNAVAILABLE as exc:
            raise LLMProviderUnavailableError(str(exc)) from exc
        text = "".join(block.text for block in response.content if block.type == "text")
        return ChatResult(
            text=text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

    def stream_tool(
        self, *, system: str, messages: list[dict[str, str]], tool: ToolSpec
    ) -> ToolCallResult:
        try:
            with self._client.messages.stream(
                model=self._model,
                max_tokens=_TOOL_CALL_MAX_TOKENS,
                system=system,
                messages=messages,  # type: ignore[arg-type]
                tools=[
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "input_schema": tool.input_schema,
                    }
                ],
                tool_choice={"type": "tool", "name": tool.name},
            ) as stream:
                final_message = stream.get_final_message()
        except _UNAVAILABLE as exc:
            raise LLMProviderUnavailableError(str(exc)) from exc

        # tool_choice forces the tool, so a response without a tool_use
        # block means the model returned something the contract does not
        # allow. Surfaced as unavailable rather than crashing on
        # StopIteration, which told the user nothing.
        tool_use_block = next(
            (block for block in final_message.content if block.type == "tool_use"), None
        )
        if tool_use_block is None:
            raise LLMProviderUnavailableError("The model returned no answer in the expected form.")
        return ToolCallResult(
            output=tool_use_block.input,
            input_tokens=final_message.usage.input_tokens,
            output_tokens=final_message.usage.output_tokens,
        )

    def stream_tools(
        self, *, system: str, messages: list[Any], tools: list[ToolSpec]
    ) -> AgentStepResult:
        try:
            with self._client.messages.stream(
                model=self._model,
                max_tokens=_TOOL_CALL_MAX_TOKENS,
                system=system,
                messages=messages,
                tools=[
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "input_schema": tool.input_schema,
                    }
                    for tool in tools
                ],
                # "any": some tool must be called, but not a specific one --
                # unlike stream_tool's forced single tool, this is exactly
                # the choice an agent loop needs. Parallel calls disabled:
                # the loop handles one tool decision per turn, and a
                # simultaneous search-and-answer call would be ambiguous
                # to execute.
                tool_choice={"type": "any", "disable_parallel_tool_use": True},
            ) as stream:
                final_message = stream.get_final_message()
        except _UNAVAILABLE as exc:
            raise LLMProviderUnavailableError(str(exc)) from exc

        tool_use_block = next(
            (block for block in final_message.content if block.type == "tool_use"), None
        )
        if tool_use_block is None:
            raise LLMProviderUnavailableError("The model returned no answer in the expected form.")
        return AgentStepResult(
            tool_name=tool_use_block.name,
            tool_input=tool_use_block.input,
            tool_use_id=tool_use_block.id,
            raw_assistant_content=final_message.content,
            input_tokens=final_message.usage.input_tokens,
            output_tokens=final_message.usage.output_tokens,
        )
