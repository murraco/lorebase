import asyncio
import hashlib

import pytest

from core.factories import ApiKeyFactory
from mcp_server.auth import LorebaseTokenVerifier

# transaction=True, not the default rolled-back-transaction wrapping:
# Django's async ORM methods (afirst/asave) run their query on a genuinely
# separate connection/thread, which can't see this test's connection's
# uncommitted transaction. Without this, a row created via the sync
# ApiKeyFactory() call is invisible to the async verify_token() lookup
# moments later -- not a bug in the code under test, a Django async+test
# isolation gap.
pytestmark = pytest.mark.django_db(transaction=True)


def _verify(token: str):
    return asyncio.run(LorebaseTokenVerifier().verify_token(token))


def test_a_valid_key_resolves_to_its_membership() -> None:
    raw_key = "lorebase_test-key"
    api_key = ApiKeyFactory(key_hash=hashlib.sha256(raw_key.encode()).hexdigest())

    access_token = _verify(raw_key)

    assert access_token is not None
    assert access_token.client_id == str(api_key.id)
    assert access_token.subject == str(api_key.membership.user_id)
    assert access_token.claims == {
        "workspace_id": str(api_key.membership.workspace_id),
        "membership_id": str(api_key.membership.id),
    }


def test_an_unknown_key_is_rejected() -> None:
    assert _verify("lorebase_not-a-real-key") is None


def test_verifying_a_key_updates_last_used_at() -> None:
    raw_key = "lorebase_test-key"
    api_key = ApiKeyFactory(
        key_hash=hashlib.sha256(raw_key.encode()).hexdigest(), last_used_at=None
    )

    _verify(raw_key)

    api_key.refresh_from_db()
    assert api_key.last_used_at is not None
