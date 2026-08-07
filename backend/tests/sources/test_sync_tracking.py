from unittest.mock import patch

import pytest

from sources.factories import SourceFactory
from sources.models import Source, SyncRun
from sources.sync import SyncStats, sync_source_with_tracking

pytestmark = pytest.mark.django_db


def test_successful_sync_records_a_run_and_marks_source_ready() -> None:
    source = SourceFactory(config={"path": "/does/not/matter"})
    stats = SyncStats(added=2, updated=1, deleted=0)

    with patch("sources.sync.sync_source", return_value=stats) as mocked:
        run = sync_source_with_tracking(source)

    mocked.assert_called_once_with(source)
    assert run.status == SyncRun.Status.SUCCESS
    assert (run.added, run.updated, run.deleted) == (2, 1, 0)
    assert run.finished_at is not None

    source.refresh_from_db()
    assert source.status == Source.Status.READY
    assert source.last_synced_at is not None
    assert source.last_error == ""


def test_failed_sync_records_a_run_and_marks_source_errored() -> None:
    source = SourceFactory(config={"path": "/does/not/matter"})

    with (
        patch("sources.sync.sync_source", side_effect=RuntimeError("disk on fire")),
        pytest.raises(RuntimeError, match="disk on fire"),
    ):
        sync_source_with_tracking(source)

    run = source.sync_runs.get()
    assert run.status == SyncRun.Status.FAILED
    assert run.error == "disk on fire"
    assert run.finished_at is not None

    source.refresh_from_db()
    assert source.status == Source.Status.ERROR
    assert source.last_error == "disk on fire"
