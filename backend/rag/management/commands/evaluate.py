import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from core.models import User, Workspace
from rag.chat.agentic import ask_agentic
from rag.chat.service import ask_with_contexts
from rag.evaluation.ragas_eval import build_sample, run_evaluation
from rag.models import Conversation

GOLDEN_SET_PATH = Path(__file__).resolve().parents[2] / "evaluation" / "golden_set.json"

_STRATEGIES = ("agentic", "direct")

# Everything to_pandas() adds beyond the golden-set input fields is a
# RAGAS metric column -- named this way so a future fifth metric shows up
# in the report automatically, without this file needing to know its name.
_NON_METRIC_COLUMNS = {"user_input", "retrieved_contexts", "response", "reference"}


class Command(BaseCommand):
    help = "Run the golden set through the live RAG pipeline and score it with RAGAS."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--workspace",
            type=str,
            default=None,
            help="Workspace id to evaluate against. Required unless exactly one workspace exists.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Only run the first N golden-set questions (cheap smoke check, not a full score).",
        )
        parser.add_argument(
            "--output",
            type=str,
            default=None,
            help="Also write a JSON report here, to diff against a later run.",
        )
        parser.add_argument(
            "--strategy",
            choices=sorted(_STRATEGIES),
            default="direct",
            help="Which pipeline to evaluate: fixed retrieval before answering (direct, "
            "default) or an LLM-controlled search tool loop (agentic).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        workspace = self._resolve_workspace(options["workspace"])
        user = User.objects.first()
        if user is None:
            raise CommandError("No user exists yet.")
        # Built here, not at module level: a dict keyed to these names at
        # import time would capture direct references to the real
        # functions, immune to tests patching
        # rag.management.commands.evaluate.ask_with_contexts/ask_agentic
        # afterward. Referencing the bare names inside handle() instead
        # means each call re-reads this module's current globals.
        ask = {"direct": ask_with_contexts, "agentic": ask_agentic}[options["strategy"]]

        golden_set = json.loads(GOLDEN_SET_PATH.read_text())
        if options["limit"]:
            golden_set = golden_set[: options["limit"]]

        rows: list[dict[str, Any]] = []
        samples = []
        for i, item in enumerate(golden_set, start=1):
            self.stdout.write(f"[{i}/{len(golden_set)}] {item['question']}")
            # A fresh Conversation per question, deleted right after: golden-set
            # questions are independent single-turn samples, not a thread, and
            # persisting them for real would mix synthetic eval traffic into
            # the dashboard's real cost/latency/query-volume metrics.
            conversation = Conversation.objects.create(workspace=workspace, user=user)
            try:
                message, results = ask(conversation, item["question"])
                # Document-level only, not expected_heading: real content is
                # legitimately covered from more than one heading in the same
                # document (a topic described both in its own section and
                # retold as an interview story, a short section merged into
                # its parent by the chunker, or the same heading landing on
                # its Spanish translation) -- expected_heading stays in the
                # golden set as human-readable provenance, not a strict gate.
                hit = any(
                    result.chunk.document.title in item["expected_document"] for result in results
                )
                samples.append(
                    build_sample(
                        question=item["question"],
                        retrieved_contexts=[result.chunk.content for result in results],
                        response=message.content,
                        reference=item["reference_answer"],
                    )
                )
                rows.append(
                    {
                        "question": item["question"],
                        "expected_document": item["expected_document"],
                        "retrieval_hit": hit,
                        # Not RAGAS's business, but exactly the cost signal
                        # agentic's variability makes worth tracking: quality
                        # gains only mean something next to what they cost.
                        "latency_ms": message.latency_ms,
                        "input_tokens": message.input_tokens,
                        "output_tokens": message.output_tokens,
                    }
                )
            finally:
                conversation.delete()

        hit_count = sum(row["retrieval_hit"] for row in rows)
        self.stdout.write("")
        self.stdout.write(f"Retrieval hit rate: {hit_count}/{len(rows)}")
        self.stdout.write("Scoring with RAGAS (one real judge-LLM call per metric per question)...")

        evaluation = run_evaluation(samples)
        scores = evaluation.to_pandas()
        metric_columns = [c for c in scores.columns if c not in _NON_METRIC_COLUMNS]
        # RAGAS preserves input order in its output, so positional alignment
        # with `rows` (built from the same `samples` list, same order) holds.
        for row, (_, score_row) in zip(rows, scores.iterrows(), strict=True):
            row.update({column: float(score_row[column]) for column in metric_columns})

        avg_latency_ms = sum(row["latency_ms"] for row in rows) / len(rows)
        avg_input_tokens = sum(row["input_tokens"] for row in rows) / len(rows)
        avg_output_tokens = sum(row["output_tokens"] for row in rows) / len(rows)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"=== Aggregate scores ({options['strategy']}) ==="))
        for column in metric_columns:
            self.stdout.write(f"  {column}: {scores[column].mean():.3f}")
        self.stdout.write(f"  avg_latency_ms: {avg_latency_ms:.0f}")
        self.stdout.write(f"  avg_input_tokens: {avg_input_tokens:.0f}")
        self.stdout.write(f"  avg_output_tokens: {avg_output_tokens:.0f}")

        if options["output"]:
            report = {
                "workspace": str(workspace.id),
                "strategy": options["strategy"],
                "golden_set_size": len(golden_set),
                "retrieval_hit_rate": hit_count / len(rows),
                "aggregate": {
                    **{column: float(scores[column].mean()) for column in metric_columns},
                    "avg_latency_ms": avg_latency_ms,
                    "avg_input_tokens": avg_input_tokens,
                    "avg_output_tokens": avg_output_tokens,
                },
                "questions": rows,
            }
            Path(options["output"]).write_text(json.dumps(report, indent=2))
            self.stdout.write(f"Report written to {options['output']}")

    def _resolve_workspace(self, workspace_id: str | None) -> Workspace:
        if workspace_id:
            try:
                return Workspace.objects.get(pk=workspace_id)
            except Workspace.DoesNotExist as exc:
                raise CommandError(f"No workspace with id {workspace_id}") from exc

        workspaces = list(Workspace.objects.all()[:2])
        if not workspaces:
            raise CommandError("No workspace exists yet.")
        if len(workspaces) > 1:
            raise CommandError("Multiple workspaces exist — pass --workspace <id> to pick one.")
        return workspaces[0]
