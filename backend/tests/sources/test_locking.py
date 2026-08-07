from django.core.cache import cache

from sources.locking import sync_lock


def test_lock_is_acquired_when_free() -> None:
    with sync_lock("source-a") as acquired:
        assert acquired is True


def test_lock_is_released_on_exit() -> None:
    with sync_lock("source-b"):
        pass

    with sync_lock("source-b") as acquired:
        assert acquired is True


def test_concurrent_lock_on_the_same_source_is_denied() -> None:
    with sync_lock("source-c") as outer:
        assert outer is True
        with sync_lock("source-c") as inner:
            assert inner is False


def test_denied_lock_does_not_release_the_holder_s_lock() -> None:
    with sync_lock("source-d") as outer:
        assert outer is True
        with sync_lock("source-d"):
            pass
        # the inner context didn't acquire it, so its exit must not have
        # released the outer one
        assert cache.get("sync-lock:source-d") is not None


def test_different_sources_do_not_contend() -> None:
    with sync_lock("source-e") as first, sync_lock("source-f") as second:
        assert first is True
        assert second is True
