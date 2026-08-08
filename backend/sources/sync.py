from dataclasses import dataclass
from pathlib import Path

from django.core.files.base import ContentFile
from django.utils import timezone

from ingestion.pipeline import process_document, purge_chunks_for_documents
from sources.connectors.base import RawDocument
from sources.connectors.registry import get_connector_class
from sources.models import Document, Source, SyncRun


def _ingest(document: Document, raw_document: RawDocument) -> None:
    canonical = _find_canonical_duplicate(document)
    if canonical is not None:
        # Same content already indexed under a different file in this
        # source — chunking and embedding it again would just duplicate
        # every resulting chunk as a retrieval candidate, for no benefit
        # (whichever one gets retrieved, the content is identical) at
        # real embedding cost. The Document row itself is kept (it's a
        # real file that exists), just left with no chunks of its own.
        document.chunks.all().delete()
        document.metadata = {**document.metadata, "duplicate_of": str(canonical.id)}
        document.save(update_fields=["metadata"])
        return

    # Optional, source-level config — content with no Markdown headings
    # (a flat journal file using bare timestamp lines, say) otherwise
    # chunks blindly by token budget with no anchor for what any given
    # chunk is about. See MarkdownParser for how it's used.
    section_boundary_pattern = document.source.config.get("section_boundary_pattern")

    if raw_document.binary is not None:
        # Cached for citation purposes; process_document parses the same
        # bytes independently, it doesn't read this back.
        filename = Path(raw_document.path).name
        document.original_file.save(filename, ContentFile(raw_document.binary), save=True)
        process_document(
            document, binary=raw_document.binary, section_boundary_pattern=section_boundary_pattern
        )
    else:
        assert raw_document.content is not None, "raw document has neither text nor binary"
        process_document(
            document, text=raw_document.content, section_boundary_pattern=section_boundary_pattern
        )


def _find_canonical_duplicate(document: Document) -> Document | None:
    """The earliest other non-deleted, non-duplicate Document in the same
    source sharing this content_hash — but only if it's genuinely earlier
    than `document` itself. Excluding documents that are themselves
    already marked as a duplicate prevents two files ingested in the same
    sync pass (near-identical created_at) from pointing at each other:
    without it, whichever gets processed second would find the first
    already flagged and — wrongly — treat that flag as disqualifying,
    looping back into a duplicate_of the other. Requiring the candidate
    to actually be earlier (not just "some other document with this
    hash") is what stops the genuinely-earliest file from getting marked
    as a duplicate of a later one it happens to be compared against.
    external_id is the tiebreaker for the rare case of an identical
    timestamp, so the result is deterministic either way.
    """
    candidate = (
        Document.objects.filter(
            source=document.source, content_hash=document.content_hash, deleted=False
        )
        .exclude(pk=document.pk)
        .exclude(metadata__has_key="duplicate_of")
        .order_by("created_at", "external_id")
        .first()
    )
    if candidate is None:
        return None

    this_key = (document.created_at, document.external_id)
    candidate_key = (candidate.created_at, candidate.external_id)
    return candidate if candidate_key < this_key else None


@dataclass
class SyncStats:
    added: int = 0
    updated: int = 0
    deleted: int = 0


def sync_source(source: Source) -> SyncStats:
    """Reconcile a Source's Documents against what its connector reports
    right now. Only touches rows whose content actually changed — running
    this twice in a row with nothing changed on disk performs zero writes.
    """
    connector_class = get_connector_class(source.type)
    connector = connector_class(source.config)
    connector.validate_config()
    connector.test_connection()

    stats = SyncStats()
    seen_external_ids: set[str] = set()

    # Includes soft-deleted rows: a document whose file reappears after
    # being removed must be revived, not collide with the unique
    # constraint on (source, external_id) by trying to create a duplicate.
    existing_by_external_id = {
        document.external_id: document for document in source.documents.all()
    }

    for raw_document in connector.fetch_documents():
        seen_external_ids.add(raw_document.external_id)
        existing = existing_by_external_id.get(raw_document.external_id)

        if existing is None:
            document = Document.objects.create(
                source=source,
                external_id=raw_document.external_id,
                path=raw_document.path,
                title=raw_document.title,
                content_hash=raw_document.content_hash,
                metadata=raw_document.metadata,
            )
            _ingest(document, raw_document)
            stats.added += 1
        elif existing.deleted or existing.content_hash != raw_document.content_hash:
            was_deleted = existing.deleted
            existing.path = raw_document.path
            existing.title = raw_document.title
            existing.content_hash = raw_document.content_hash
            existing.metadata = raw_document.metadata
            existing.deleted = False
            existing.version += 1
            existing.save()
            _ingest(existing, raw_document)
            stats.added += 1 if was_deleted else 0
            stats.updated += 0 if was_deleted else 1
        # else: content_hash matches and it wasn't deleted -> unchanged, no write.

    missing_external_ids = {
        external_id
        for external_id, document in existing_by_external_id.items()
        if not document.deleted
    } - seen_external_ids
    if missing_external_ids:
        missing_document_ids = [
            document.id
            for external_id, document in existing_by_external_id.items()
            if external_id in missing_external_ids
        ]
        stats.deleted = Document.objects.filter(
            source=source, external_id__in=missing_external_ids, deleted=False
        ).update(deleted=True)
        purge_chunks_for_documents(missing_document_ids)

    return stats


def sync_source_with_tracking(source: Source) -> SyncRun:
    """Wraps sync_source() with the observability the plain function
    deliberately doesn't have: a SyncRun row recording the attempt, and
    Source.status/last_error reflecting the outcome. Kept independent of
    Celery so it's testable without any task machinery — the task in
    sources/tasks.py is a thin wrapper adding only the lock and retries.
    """
    source.status = Source.Status.SYNCING
    source.save(update_fields=["status"])

    run = SyncRun.objects.create(source=source, status=SyncRun.Status.RUNNING)

    try:
        stats = sync_source(source)
    except Exception as exc:
        run.status = SyncRun.Status.FAILED
        run.error = str(exc)
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "error", "finished_at"])

        source.status = Source.Status.ERROR
        source.last_error = str(exc)
        source.save(update_fields=["status", "last_error"])
        raise

    run.status = SyncRun.Status.SUCCESS
    run.added = stats.added
    run.updated = stats.updated
    run.deleted = stats.deleted
    run.finished_at = timezone.now()
    run.save(update_fields=["status", "added", "updated", "deleted", "finished_at"])

    source.status = Source.Status.READY
    source.last_synced_at = timezone.now()
    source.last_error = ""
    source.save(update_fields=["status", "last_synced_at", "last_error"])

    return run
