from dataclasses import dataclass

from rag.llm.base import ChatResult, LLMProvider, ToolCallResult, ToolSpec


@dataclass
class _RecordedCall:
    kind: str
    system: str
    messages: list[dict[str, str]]
    tool: ToolSpec | None = None


class FakeLLMProvider(LLMProvider):
    """No network calls. Tests configure exactly what it should return —
    there's no attempt to simulate real model behavior (unlike
    FakeEmbeddingProvider, which at least has to produce dimensionally
    valid vectors, a fake LLM has no equivalent structural contract worth
    faking).
    """

    def __init__(self) -> None:
        self.next_chat_result = ChatResult(text="", input_tokens=0, output_tokens=0)
        self.next_tool_result = ToolCallResult(output={}, input_tokens=0, output_tokens=0)
        self.calls: list[_RecordedCall] = []

    def chat(self, *, system: str, messages: list[dict[str, str]]) -> ChatResult:
        self.calls.append(_RecordedCall(kind="chat", system=system, messages=messages))
        return self.next_chat_result

    def stream_tool(
        self, *, system: str, messages: list[dict[str, str]], tool: ToolSpec
    ) -> ToolCallResult:
        self.calls.append(
            _RecordedCall(kind="stream_tool", system=system, messages=messages, tool=tool)
        )
        return self.next_tool_result
