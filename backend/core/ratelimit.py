from collections.abc import Callable
from functools import wraps
from typing import Concatenate, ParamSpec

from django.core.cache import cache
from django.http import HttpRequest, HttpResponseBase, JsonResponse

_P = ParamSpec("_P")
_View = Callable[Concatenate[HttpRequest, _P], HttpResponseBase]


def rate_limit(*, scope: str, limit: int, window_seconds: int) -> Callable[[_View[_P]], _View[_P]]:
    """Fixed-window rate limit, per authenticated user, backed by the
    Redis cache (CACHES["default"]). For the small number of endpoints
    that cost real money per call -- the chat endpoint (an Anthropic API
    call) is the only one today. DRF's own throttle classes don't apply
    here: this decorates a plain Django view, not a DRF APIView.

    cache.incr() is atomic (a single Redis INCR), so concurrent requests
    can't race past the limit the way a naive get-then-set would. The one
    accepted race is at the very start of a new window: two concurrent
    requests can both see a missing key and both initialize it to 1,
    letting one extra request through that minute -- a fixed-window
    counter's known, minor imprecision, not worth a more complex
    algorithm (sliding window, token bucket) for this project's scale.
    """

    def decorator(view_func: _View[_P]) -> _View[_P]:
        @wraps(view_func)
        def wrapped(request: HttpRequest, *args: _P.args, **kwargs: _P.kwargs) -> HttpResponseBase:
            key = f"ratelimit:{scope}:{request.user.pk}"
            try:
                count = cache.incr(key)
            except ValueError:
                cache.set(key, 1, timeout=window_seconds)
                count = 1
            if count > limit:
                return JsonResponse(
                    {"detail": "Too many requests. Try again in a moment."}, status=429
                )
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator
