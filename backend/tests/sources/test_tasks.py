from pathlib import Path

import pytest
from django.core.cache import cache

from sources.factories import SourceFactory
from sources.models import Source, SyncRun
from sources.tasks import sync_source_task

pytestmark = pytest.mark.django_db


def test_task_runs_a_real_sync_end_to_end(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("# Title\n\nsome content")
    source = SourceFactory(config={"path": str(tmp_path)})

    result = sync_source_task.delay(str(source.id)).get()

    assert result == {"added": 1, "updated": 0, "deleted": 0}
    assert source.sync_runs.get().status == SyncRun.Status.SUCCESS

    source.refresh_from_db()
    assert source.status == Source.Status.READY

    # sync_source_task chains backfill_embeddings_task.delay() on success;
    # CELERY_TASK_ALWAYS_EAGER runs that inline too, so by the time .get()
    # above returned, the newly created chunk should already be embedded.
    document = source.documents.get()
    assert not document.chunks.filter(embedding__isnull=True).exists()


def test_task_skips_when_a_sync_is_already_running(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("content")
    source = SourceFactory(config={"path": str(tmp_path)})
    cache.add(f"sync-lock:{source.id}", "1", timeout=60)

    result = sync_source_task.delay(str(source.id)).get()

    assert result == {"skipped": True}
    assert not source.sync_runs.exists()

    cache.delete(f"sync-lock:{source.id}")
