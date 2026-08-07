import anthropic
from django.conf import settings

from rag.llm.base import ChatResult, LLMProvider, ToolCallResult, ToolSpec

_CHAT_MAX_TOKENS = 1024
_TOOL_CALL_MAX_TOKENS = 2048


class AnthropicProvider(LLMProvider):
    def __init__(self) -> None:
        self._client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, max_retries=3)
        self._model = settings.LLM_MODEL

    def chat(self, *, system: str, messages: list[dict[str, str]]) -> ChatResult:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=_CHAT_MAX_TOKENS,
            system=system,
            messages=messages,  # type: ignore[arg-type]
        )
        text = "".join(
            block.text for block in response.content if block.type == "text"
        )
        return ChatResult(
            text=text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

    def stream_tool(
        self, *, system: str, messages: list[dict[str, str]], tool: ToolSpec
    ) -> ToolCallResult:
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

        tool_use_block = next(
            block for block in final_message.content if block.type == "tool_use"
        )
        return ToolCallResult(
            output=tool_use_block.input,
            input_tokens=final_message.usage.input_tokens,
            output_tokens=final_message.usage.output_tokens,
        )
