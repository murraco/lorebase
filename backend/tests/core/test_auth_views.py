import json

import pytest
from django.test import Client

from core.factories import MembershipFactory, UserFactory

pytestmark = pytest.mark.django_db


def test_csrf_view_sets_a_csrf_cookie() -> None:
    response = Client().get("/api/auth/csrf/")

    assert response.status_code == 200
    assert "csrftoken" in response.cookies
    assert response.json()["csrfToken"]


def test_login_with_correct_credentials_starts_a_session() -> None:
    user = UserFactory()
    user.set_password("correct horse battery staple")
    user.save()
    client = Client(enforce_csrf_checks=False)

    response = client.post(
        "/api/auth/login/",
        data=json.dumps({"username": user.username, "password": "correct horse battery staple"}),
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json()["username"] == user.username
    assert "_auth_user_id" in client.session


def test_login_with_wrong_password_is_rejected() -> None:
    user = UserFactory()
    user.set_password("correct horse battery staple")
    user.save()
    client = Client(enforce_csrf_checks=False)

    response = client.post(
        "/api/auth/login/",
        data=json.dumps({"username": user.username, "password": "wrong"}),
        content_type="application/json",
    )

    assert response.status_code == 400
    assert "_auth_user_id" not in client.session


def test_me_returns_401_when_not_authenticated() -> None:
    response = Client().get("/api/auth/me/")

    assert response.status_code == 401


def test_me_returns_the_current_user_when_authenticated() -> None:
    user = UserFactory()
    client = Client()
    client.force_login(user)

    response = client.get("/api/auth/me/")

    assert response.status_code == 200
    assert response.json() == {"id": str(user.id), "username": user.username, "workspaces": []}


def test_me_includes_the_users_workspaces() -> None:
    membership = MembershipFactory()
    client = Client()
    client.force_login(membership.user)

    response = client.get("/api/auth/me/")

    assert response.json()["workspaces"] == [
        {"id": str(membership.workspace_id), "name": membership.workspace.name}
    ]


def test_logout_ends_the_session() -> None:
    user = UserFactory()
    user.set_password("correct horse battery staple")
    user.save()
    client = Client(enforce_csrf_checks=False)
    client.post(
        "/api/auth/login/",
        data=json.dumps({"username": user.username, "password": "correct horse battery staple"}),
        content_type="application/json",
    )

    response = client.post("/api/auth/logout/")

    assert response.status_code == 200
    assert "_auth_user_id" not in client.session
