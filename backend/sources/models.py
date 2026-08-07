from django.db import models

from core.models import BaseModel, Workspace


class Source(BaseModel):
    class SourceType(models.TextChoices):
        LOCAL_FOLDER = "local_folder", "Local folder"
        GITHUB = "github", "GitHub"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SYNCING = "syncing", "Syncing"
        READY = "ready", "Ready"
        ERROR = "error", "Error"

    workspace = models.ForeignKey(
        Workspace, on_delete=models.CASCADE, related_name="sources"
    )
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=20, choices=SourceType.choices)
    config = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    last_synced_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, default="")

    def __str__(self) -> str:
        return self.name


class Document(BaseModel):
    source = models.ForeignKey(
        Source, on_delete=models.CASCADE, related_name="documents"
    )
    # Connector-specific identity used to detect the same document across
    # syncs (e.g. a file path for local_folder, "repo@path" for GitHub).
    external_id = models.CharField(max_length=1024)
    path = models.CharField(max_length=1024)
    title = models.CharField(max_length=500, blank=True, default="")
    content_hash = models.CharField(max_length=64)
    version = models.PositiveIntegerField(default=1)
    deleted = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["source", "external_id"], name="unique_document_per_source"
            )
        ]
        indexes = [
            models.Index(fields=["source", "content_hash"]),
            models.Index(fields=["source", "deleted"]),
        ]

    def __str__(self) -> str:
        return self.title or self.path
