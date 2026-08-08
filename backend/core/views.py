import json
from typing import Any

from django.contrib.auth import authenticate, login, logout
from django.http import HttpRequest, JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.http import require_GET, require_POST

from core.models import User


def _serialize_user(user: User) -> dict[str, Any]:
    return {
        "id": str(user.id),
        "username": user.username,
        # The SPA needs a workspace id for anything it creates (a Source,
        # a Conversation) — there's no dedicated /api/workspaces/
        # endpoint, so this is the only place it can discover one.
        "workspaces": [
            {"id": str(membership.workspace_id), "name": membership.workspace.name}
            for membership in user.memberships.select_related("workspace")
        ],
    }


@require_GET
def csrf_view(request: HttpRequest) -> JsonResponse:
    """Sets the csrftoken cookie. The SPA calls this once before its first
    POST (login) so the CSRF middleware has a token to check the
    X-CSRFToken header against — otherwise there's no cookie yet for an
    unauthenticated visitor to read.
    """
    return JsonResponse({"csrfToken": get_token(request)})


@require_GET
def me_view(request: HttpRequest) -> JsonResponse:
    """Lets the SPA check for an existing session on page load, without
    guessing from a 401/403 on some unrelated endpoint.
    """
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Not authenticated."}, status=401)
    return JsonResponse(_serialize_user(request.user))


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
    return JsonResponse(_serialize_user(user))


@require_POST
def logout_view(request: HttpRequest) -> JsonResponse:
    logout(request)
    return JsonResponse({"detail": "Logged out."})
