from typing import Any

from django.core.management.base import BaseCommand, CommandError

from core.models import User, Workspace
from rag.chat.service import ask
from rag.models import Conversation


class Command(BaseCommand):
    help = "Ask a question against the knowledge base, without needing the UI."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("question", type=str)
        parser.add_argument(
            "--conversation",
            type=str,
            default=None,
            help="Existing conversation id, to continue a thread (and exercise query rewriting).",
        )
        parser.add_argument(
            "--workspace",
            type=str,
            default=None,
            help="Workspace id to ask in. Required unless exactly one workspace exists.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        conversation = self._resolve_conversation(options["conversation"], options["workspace"])
        message = ask(conversation, options["question"])

        self.stdout.write(self.style.SUCCESS(message.content))
        self.stdout.write("")
        self.stdout.write(f"conversation: {conversation.id}")
        for citation in message.citations.select_related("chunk__document"):
            chunk = citation.chunk
            self.stdout.write(
                f"  - {chunk.document.path} (lines {chunk.start_line}-{chunk.end_line})"
            )

    def _resolve_conversation(
        self, conversation_id: str | None, workspace_id: str | None
    ) -> Conversation:
        if conversation_id:
            try:
                return Conversation.objects.get(pk=conversation_id)
            except Conversation.DoesNotExist as exc:
                raise CommandError(f"No conversation with id {conversation_id}") from exc

        workspace = self._resolve_workspace(workspace_id)
        user = User.objects.first()
        if user is None:
            raise CommandError("No user exists yet.")
        return Conversation.objects.create(workspace=workspace, user=user)

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
            raise CommandError(
                "Multiple workspaces exist — pass --workspace <id> to pick one."
            )
        return workspaces[0]
