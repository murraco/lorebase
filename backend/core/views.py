import json

from django.contrib.auth import authenticate, login, logout
from django.http import HttpRequest, JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.http import require_GET, require_POST


@require_GET
def csrf_view(request: HttpRequest) -> JsonResponse:
    """Sets the csrftoken cookie. The SPA calls this once before its first
    POST (login) so the CSRF middleware has a token to check the
    X-CSRFToken header against — otherwise there's no cookie yet for an
    unauthenticated visitor to read.
    """
    return JsonResponse({"csrfToken": get_token(request)})


@require_POST
def login_view(request: HttpRequest) -> JsonResponse:
    try:
        data = json.loads(request.body)
        username = data["username"]
        password = data["password"]
    except (json.JSONDecodeError, KeyError):
        return JsonResponse({"detail": "Expected 'username' and 'password'."}, status=400)

    user = authenticate(request, username=username, password=password)
    if user is None:
        return JsonResponse({"detail": "Invalid credentials."}, status=400)

    login(request, user)
    return JsonResponse({"id": str(user.id), "username": user.username})


@require_POST
def logout_view(request: HttpRequest) -> JsonResponse:
    logout(request)
    return JsonResponse({"detail": "Logged out."})
