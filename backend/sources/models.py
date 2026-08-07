from django.db import models

from core.models import BaseModel, Workspace


def document_upload_path(instance: "Document", filename: str) -> str:
    # Namespaced by source: two different sources could otherwise contain
    # a same-named file (e.g. two PDF folders both with a "resume.pdf").
    return f"documents/{instance.source_id}/{filename}"


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
    # Only set for binary sources (PDFs) — cached so it can be displayed or
    # cited precisely later. Text-based documents (Markdown) have no
    # original binary to cache; the source file on disk is already the
    # original.
    original_file = models.FileField(upload_to=document_upload_path, null=True, blank=True)

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


class SyncRun(BaseModel):
    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"

    source = models.ForeignKey(Source, on_delete=models.CASCADE, related_name="sync_runs")
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RUNNING)
    added = models.PositiveIntegerField(default=0)
    updated = models.PositiveIntegerField(default=0)
    deleted = models.PositiveIntegerField(default=0)
    error = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-started_at"]

    def __str__(self) -> str:
        return f"{self.source} @ {self.started_at:%Y-%m-%d %H:%M}"
