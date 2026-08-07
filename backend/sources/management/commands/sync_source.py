from typing import Any

from django.core.management.base import BaseCommand, CommandError

from sources.connectors.base import ConnectorConfigError, ConnectorConnectionError
from sources.models import Source
from sources.sync import sync_source


class Command(BaseCommand):
    help = "Sync a Source's Documents against its connector."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("source_id", type=str)

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            source = Source.objects.get(pk=options["source_id"])
        except Source.DoesNotExist as exc:
            raise CommandError(f"No source with id {options['source_id']}") from exc

        try:
            stats = sync_source(source)
        except (ConnectorConfigError, ConnectorConnectionError) as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"{source.name}: {stats.added} added, {stats.updated} updated, "
                f"{stats.deleted} deleted"
            )
        )
