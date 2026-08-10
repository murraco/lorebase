import hashlib
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from core.factories import MembershipFactory
from core.models import ApiKey

pytestmark = pytest.mark.django_db


def test_creates_a_key_hashed_and_tied_to_the_membership() -> None:
    membership = MembershipFactory()
    out = StringIO()

    call_command(
        "create_mcp_api_key", "--membership", str(membership.id), "--name", "Test key", stdout=out
    )

    api_key = ApiKey.objects.get(membership=membership)
    assert api_key.name == "Test key"

    output = out.getvalue()
    assert "lorebase_" in output
    raw_key = next(line for line in output.splitlines() if line.startswith("lorebase_"))
    # The command must never print anything the DB could be searched by --
    # only the raw key, which is unrecoverable once this output is gone.
    assert api_key.key_hash == hashlib.sha256(raw_key.encode()).hexdigest()
    assert api_key.key_hash not in output


def test_unknown_membership_raises() -> None:
    with pytest.raises(CommandError, match="No membership"):
        call_command(
            "create_mcp_api_key",
            "--membership",
            "00000000-0000-0000-0000-000000000000",
            "--name",
            "Test key",
            stdout=StringIO(),
        )
