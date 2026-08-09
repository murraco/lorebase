from django.apps import AppConfig


class SourcesConfig(AppConfig):
    name = "sources"

    def ready(self) -> None:
        # Importing connector modules registers them via the
        # @register_connector decorator (a side effect of import). This is
        # the one place that import is guaranteed to happen in every
        # process — runserver, a Celery worker, a management command —
        # instead of relying on some other module happening to import it
        # first.
        from sources.connectors import github, local_folder  # noqa: F401
