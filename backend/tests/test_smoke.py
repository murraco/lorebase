from django.conf import settings
from django.test import Client
from django.urls import reverse


def test_test_settings_are_active() -> None:
    assert settings.DEBUG is False
    assert settings.PASSWORD_HASHERS == ["django.contrib.auth.hashers.MD5PasswordHasher"]


def test_admin_login_page_resolves() -> None:
    """Exercises URLConf, middleware, and templates together."""
    response = Client().get(reverse("admin:login"))

    assert response.status_code == 200
