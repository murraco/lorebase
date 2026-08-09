import json
from io import StringIO
from unittest.mock import Mock, patch

import pandas as pd
import pytest
from django.core.management import call_command

from core.factories import UserFactory, WorkspaceFactory
from ingestion.factories import ChunkFactory
from rag.models import Conversation
from rag.retrieval.base import RetrievalResult
from sources.factories import DocumentFactory

pytestmark = pytest.mark.django_db


def _write_golden_set(tmp_path, entries):
    path = tmp_path / "golden_set.json"
    path.write_text(json.dumps(entries))
    return path


def _fake_scores(n: int) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "user_input": [f"q{i}" for i in range(n)],
            "retrieved_contexts": [["ctx"]] * n,
            "response": ["resp"] * n,
            "reference": ["ref"] * n,
            "faithfulness": [0.8] * n,
        }
    )


def test_evaluate_reports_retrieval_hit_rate_and_writes_a_report(tmp_path) -> None:
    workspace = WorkspaceFactory()
    UserFactory()
    hit_document = DocumentFactory(source__workspace=workspace, title="career_notes")
    hit_chunk = ChunkFactory(
        document=hit_document, content="the answer", heading_path="Career Notes > Backend"
    )
    golden_path = _write_golden_set(
        tmp_path,
        [
            {
                "question": "What tech stack does the backend use?",
                "expected_document": ["career_notes"],
                "expected_heading": "Backend",
                "reference_answer": "Django and Postgres.",
            },
            {
                "question": "A question retrieval will miss.",
                "expected_document": ["some_other_doc"],
                "expected_heading": "Nowhere",
                "reference_answer": "Doesn't matter.",
            },
        ],
    )

    fake_message = Mock(content="An answer.", latency_ms=100, input_tokens=200, output_tokens=50)
    fake_results = [RetrievalResult(chunk=hit_chunk, score=0.9)]
    fake_evaluation = Mock()
    fake_evaluation.to_pandas.return_value = _fake_scores(2)

    output_path = tmp_path / "report.json"
    out = StringIO()
    with (
        patch("rag.management.commands.evaluate.GOLDEN_SET_PATH", golden_path),
        patch(
            "rag.management.commands.evaluate.ask_with_contexts",
            return_value=(fake_message, fake_results),
        ),
        patch("rag.management.commands.evaluate.run_evaluation", return_value=fake_evaluation),
    ):
        call_command(
            "evaluate",
            "--workspace",
            str(workspace.id),
            "--output",
            str(output_path),
            stdout=out,
        )

    output = out.getvalue()
    # Both questions get the same stubbed retrieval result (the hit_chunk),
    # so only the first (whose expected_document/expected_heading actually
    # match it) counts as a hit -- the second's don't, on purpose.
    assert "Retrieval hit rate: 1/2" in output
    assert "faithfulness: 0.800" in output

    report = json.loads(output_path.read_text())
    assert report["strategy"] == "direct"
    assert report["retrieval_hit_rate"] == 0.5
    assert report["aggregate"] == {
        "faithfulness": 0.8,
        "avg_latency_ms": 100.0,
        "avg_input_tokens": 200.0,
        "avg_output_tokens": 50.0,
    }
    assert [q["retrieval_hit"] for q in report["questions"]] == [True, False]

    # Every golden-set question gets its own scratch conversation, deleted
    # right after -- eval runs must not pollute real conversation history.
    assert Conversation.objects.count() == 0


def test_evaluate_respects_limit(tmp_path) -> None:
    workspace = WorkspaceFactory()
    UserFactory()
    document = DocumentFactory(source__workspace=workspace, title="doc")
    chunk = ChunkFactory(document=document, heading_path="doc > A")
    golden_path = _write_golden_set(
        tmp_path,
        [
            {
                "question": f"question {i}",
                "expected_document": ["doc"],
                "expected_heading": "A",
                "reference_answer": "ref",
            }
            for i in range(5)
        ],
    )

    fake_message = Mock(content="An answer.", latency_ms=100, input_tokens=200, output_tokens=50)
    fake_results = [RetrievalResult(chunk=chunk, score=0.9)]
    fake_evaluation = Mock()

    with (
        patch("rag.management.commands.evaluate.GOLDEN_SET_PATH", golden_path),
        patch(
            "rag.management.commands.evaluate.ask_with_contexts",
            return_value=(fake_message, fake_results),
        ) as mock_ask,
        patch(
            "rag.management.commands.evaluate.run_evaluation", return_value=fake_evaluation
        ) as mock_eval,
    ):
        fake_evaluation.to_pandas.return_value = _fake_scores(2)
        call_command(
            "evaluate", "--workspace", str(workspace.id), "--limit", "2", stdout=StringIO()
        )

    assert mock_ask.call_count == 2
    (call,) = mock_eval.call_args_list
    assert len(call.args[0]) == 2


def test_evaluate_strategy_agentic_calls_ask_agentic_not_ask_with_contexts(tmp_path) -> None:
    workspace = WorkspaceFactory()
    UserFactory()
    document = DocumentFactory(source__workspace=workspace, title="doc")
    chunk = ChunkFactory(document=document, heading_path="doc > A")
    golden_path = _write_golden_set(
        tmp_path,
        [
            {
                "question": "q",
                "expected_document": ["doc"],
                "expected_heading": "A",
                "reference_answer": "ref",
            }
        ],
    )

    fake_message = Mock(content="An answer.", latency_ms=9000, input_tokens=500, output_tokens=80)
    fake_results = [RetrievalResult(chunk=chunk, score=0.9)]
    fake_evaluation = Mock()
    fake_evaluation.to_pandas.return_value = _fake_scores(1)

    with (
        patch("rag.management.commands.evaluate.GOLDEN_SET_PATH", golden_path),
        patch(
            "rag.management.commands.evaluate.ask_agentic",
            return_value=(fake_message, fake_results),
        ) as mock_agentic,
        patch("rag.management.commands.evaluate.ask_with_contexts") as mock_direct,
        patch("rag.management.commands.evaluate.run_evaluation", return_value=fake_evaluation),
    ):
        out = StringIO()
        call_command(
            "evaluate", "--workspace", str(workspace.id), "--strategy", "agentic", stdout=out
        )

    assert mock_agentic.call_count == 1
    mock_direct.assert_not_called()
    assert "=== Aggregate scores (agentic) ===" in out.getvalue()
