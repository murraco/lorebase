from rag.llm.base import ToolSpec
from rag.retrieval.base import RetrievalResult

SYSTEM_PROMPT = (
    "You answer questions using ONLY the numbered notes provided below. "
    "Every claim in your answer must be grounded in these notes. Call the "
    "provide_answer tool with your answer and the list of note IDs you "
    "actually used to support it — never cite an ID that wasn't given to "
    "you. If the notes don't contain the answer, say so honestly instead "
    "of guessing."
)

ANSWER_TOOL = ToolSpec(
    name="provide_answer",
    description="Provide the answer to the user's question, citing which notes were used.",
    input_schema={
        "type": "object",
        "properties": {
            "answer": {
                "type": "string",
                "description": "The answer to the user's question.",
            },
            "cited_chunk_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "IDs of the notes actually used to support the answer.",
            },
        },
        "required": ["answer", "cited_chunk_ids"],
    },
)


def build_context(results: list[RetrievalResult]) -> str:
    return "\n\n".join(
        f"[{result.chunk.id}] (from {result.chunk.document.path})\n{result.chunk.content}"
        for result in results
    )
