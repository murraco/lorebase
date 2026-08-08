from django.conf import settings
from django.db import models

from core.models import BaseModel, Workspace
from ingestion.models import Chunk


class Conversation(BaseModel):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="conversations")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="conversations"
    )
    title = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.title or str(self.id)


class Message(BaseModel):
    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    content = models.TextField()
    # Only meaningful for assistant messages — null for user messages,
    # which never involve an LLM call of their own.
    latency_ms = models.PositiveIntegerField(null=True, blank=True)
    input_tokens = models.PositiveIntegerField(null=True, blank=True)
    output_tokens = models.PositiveIntegerField(null=True, blank=True)
    cost = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"{self.role}: {self.content[:50]}"


class Citation(BaseModel):
    """Links a Message to a Chunk it actually cited. Only ever created for
    chunk_ids the server verified were part of the context sent to the
    LLM for that message — never persisted from an unvalidated model claim.
    """

    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="citations")
    chunk = models.ForeignKey(Chunk, on_delete=models.CASCADE, related_name="citations")
    # 1-based position of this chunk in the context that was sent to the
    # model, so a reader can tell the top hit from the fifth one. Also
    # what Meta.ordering sorts on: without it the queryset order was
    # undefined, which is fine for unordered chips but wrong the moment
    # citations are numbered.
    rank = models.PositiveIntegerField(default=0)
    # The retriever's score for that chunk. Nullable because it is not
    # comparable across strategies — a cross-encoder logit, an RRF sum and
    # a ts_rank value live on different scales — so it is provenance to
    # show, never a number to threshold on.
    score = models.FloatField(null=True, blank=True)

    class Meta:
        ordering = ["rank"]
        constraints = [
            models.UniqueConstraint(
                fields=["message", "chunk"], name="unique_citation_per_message_chunk"
            )
        ]

    def __str__(self) -> str:
        return f"{self.message_id} -> {self.chunk_id}"
