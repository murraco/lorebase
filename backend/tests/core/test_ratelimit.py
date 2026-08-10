import pytest
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse
from django.test import RequestFactory

from core.factories import UserFactory
from core.ratelimit import rate_limit

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


def _make_request(user) -> HttpRequest:
    request = RequestFactory().post("/whatever/")
    request.user = user
    return request


def test_requests_under_the_limit_pass_through() -> None:
    calls = []

    @rate_limit(scope="test-scope", limit=3, window_seconds=60)
    def view(request: HttpRequest) -> HttpResponse:
        calls.append(1)
        return HttpResponse("ok")

    user = UserFactory()
    for _ in range(3):
        response = view(_make_request(user))
        assert response.status_code == 200

    assert len(calls) == 3


def test_the_request_over_the_limit_is_rejected_with_429() -> None:
    @rate_limit(scope="test-scope", limit=2, window_seconds=60)
    def view(request: HttpRequest) -> HttpResponse:
        return HttpResponse("ok")

    user = UserFactory()
    view(_make_request(user))
    view(_make_request(user))
    response = view(_make_request(user))

    assert response.status_code == 429


def test_the_limit_is_tracked_per_user_not_globally() -> None:
    @rate_limit(scope="test-scope", limit=1, window_seconds=60)
    def view(request: HttpRequest) -> HttpResponse:
        return HttpResponse("ok")

    first_user, second_user = UserFactory(), UserFactory()

    assert view(_make_request(first_user)).status_code == 200
    # Would 429 if the counter were shared across users instead of keyed
    # by user id -- the whole point of "per user" rate limiting.
    assert view(_make_request(second_user)).status_code == 200


def test_the_limit_is_tracked_per_scope_not_shared_across_decorated_views() -> None:
    @rate_limit(scope="scope-a", limit=1, window_seconds=60)
    def view_a(request: HttpRequest) -> HttpResponse:
        return HttpResponse("ok")

    @rate_limit(scope="scope-b", limit=1, window_seconds=60)
    def view_b(request: HttpRequest) -> HttpResponse:
        return HttpResponse("ok")

    user = UserFactory()

    assert view_a(_make_request(user)).status_code == 200
    # A different endpoint's limit must not be consumed by this one.
    assert view_b(_make_request(user)).status_code == 200
