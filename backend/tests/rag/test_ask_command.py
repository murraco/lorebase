from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command

from core.factories import UserFactory, WorkspaceFactory
from ingestion.factories import ChunkFactory
from rag.llm.base import ToolCallResult
from rag.llm.factory import get_llm_provider
from rag.models import Conversation
from rag.retrieval.base import RetrievalResult
from sources.factories import DocumentFactory

pytestmark = pytest.mark.django_db


class _StubRetriever:
    def __init__(self, results):
        self._results = results

    def search(self, query, *, workspace_id, top_k=10, filters=None):
        return self._results


@pytest.fixture(autouse=True)
def _clear_llm_cache():
    get_llm_provider.cache_clear()
    yield
    get_llm_provider.cache_clear()


def test_ask_command_creates_a_conversation_and_prints_citations() -> None:
    workspace = WorkspaceFactory()
    UserFactory()
    document = DocumentFactory(source__workspace=workspace, path="notes/rag.md")
    chunk = ChunkFactory(document=document, content="content", start_line=1, end_line=4)

    fake_llm = get_llm_provider()
    fake_llm.next_tool_result = ToolCallResult(
        output={"answer": "the answer", "cited_chunk_ids": [str(chunk.id)]},
        input_tokens=1,
        output_tokens=1,
    )

    out = StringIO()
    with patch(
        "rag.chat.service.get_retriever",
        return_value=_StubRetriever([RetrievalResult(chunk=chunk, score=1.0)]),
    ):
        call_command("ask", "some question", stdout=out)

    output = out.getvalue()
    assert "the answer" in output
    assert "notes/rag.md" in output
    assert Conversation.objects.count() == 1
