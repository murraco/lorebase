from dataclasses import dataclass

from sources.connectors.registry import get_connector_class
from sources.models import Document, Source


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
            Document.objects.create(
                source=source,
                external_id=raw_document.external_id,
                path=raw_document.path,
                title=raw_document.title,
                content_hash=raw_document.content_hash,
                metadata=raw_document.metadata,
            )
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
            stats.added += 1 if was_deleted else 0
            stats.updated += 0 if was_deleted else 1
        # else: content_hash matches and it wasn't deleted -> unchanged, no write.

    missing_external_ids = {
        external_id
        for external_id, document in existing_by_external_id.items()
        if not document.deleted
    } - seen_external_ids
    if missing_external_ids:
        stats.deleted = Document.objects.filter(
            source=source, external_id__in=missing_external_ids, deleted=False
        ).update(deleted=True)

    return stats
