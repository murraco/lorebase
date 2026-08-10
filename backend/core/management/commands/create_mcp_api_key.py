import hashlib
import secrets
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from core.models import ApiKey, Membership

_KEY_PREFIX = "lorebase_"


class Command(BaseCommand):
    help = (
        "Create an API key for the MCP server, tied to a Membership. "
        "The raw key is shown once, here, and is unrecoverable after that -- "
        "only its hash is ever stored."
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--membership", required=True, help="Membership id this key belongs to."
        )
        parser.add_argument(
            "--name",
            required=True,
            help="A human label for the key, e.g. 'Claude Code on laptop'.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            membership = Membership.objects.get(pk=options["membership"])
        except Membership.DoesNotExist as exc:
            raise CommandError(f"No membership with id {options['membership']}") from exc

        raw_key = _KEY_PREFIX + secrets.token_urlsafe(32)
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        ApiKey.objects.create(membership=membership, name=options["name"], key_hash=key_hash)

        self.stdout.write(
            self.style.SUCCESS("API key created. Copy it now -- it will not be shown again:")
        )
        self.stdout.write("")
        self.stdout.write(raw_key)
