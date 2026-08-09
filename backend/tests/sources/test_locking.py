from django.core.cache import cache

from sources.locking import clear_cancel, is_cancel_requested, request_cancel, sync_lock


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


def test_cancel_is_not_requested_by_default() -> None:
    assert is_cancel_requested("source-g") is False


def test_cancel_flag_is_visible_once_requested() -> None:
    request_cancel("source-h")

    assert is_cancel_requested("source-h") is True


def test_clear_cancel_removes_the_flag() -> None:
    request_cancel("source-i")
    clear_cancel("source-i")

    assert is_cancel_requested("source-i") is False


def test_cancel_flag_is_scoped_per_source() -> None:
    request_cancel("source-j")

    assert is_cancel_requested("source-k") is False
