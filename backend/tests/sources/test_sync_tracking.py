from unittest.mock import patch

import pytest

from sources.factories import SourceFactory
from sources.locking import is_cancel_requested, request_cancel
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


def test_cancelled_sync_is_recorded_but_not_treated_as_a_failure() -> None:
    """Whatever a cancelled sync ingested before the cancellation point is
    real and queryable — same as any other partial sync. Only the SyncRun
    remembers it didn't run to completion."""
    source = SourceFactory(config={"path": "/does/not/matter"})
    stats = SyncStats(added=1, updated=0, deleted=0, cancelled=True)

    with patch("sources.sync.sync_source", return_value=stats):
        run = sync_source_with_tracking(source)

    assert run.status == SyncRun.Status.CANCELLED
    assert run.added == 1
    assert run.finished_at is not None

    source.refresh_from_db()
    assert source.status == Source.Status.READY
    assert source.last_error == ""
    assert is_cancel_requested(source.id) is False


def test_stale_cancel_flag_does_not_affect_a_new_sync() -> None:
    """A cancel requested for a previous run must not still be armed the
    next time this source syncs."""
    source = SourceFactory(config={"path": "/does/not/matter"})
    request_cancel(source.id)
    stats = SyncStats(added=1, updated=0, deleted=0)

    with patch("sources.sync.sync_source", return_value=stats):
        run = sync_source_with_tracking(source)

    assert run.status == SyncRun.Status.SUCCESS
    source.refresh_from_db()
    assert source.status == Source.Status.READY
