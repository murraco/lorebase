from dataclasses import dataclass
from pathlib import Path

from django.core.files.base import ContentFile
from django.utils import timezone

from ingestion.pipeline import process_document, purge_chunks_for_documents
from sources.connectors.base import RawDocument
from sources.connectors.registry import get_connector_class
from sources.models import Document, Source, SyncRun


def _ingest(document: Document, raw_document: RawDocument) -> None:
    if raw_document.binary is not None:
        # Cached for citation purposes; process_document parses the same
        # bytes independently, it doesn't read this back.
        filename = Path(raw_document.path).name
        document.original_file.save(filename, ContentFile(raw_document.binary), save=True)
        process_document(document, binary=raw_document.binary)
    else:
        assert raw_document.content is not None, "raw document has neither text nor binary"
        process_document(document, text=raw_document.content)


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
