from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "core"

    def ready(self) -> None:
        # Every process that loads Django settings runs this — runserver,
        # a Celery worker, a management command — so it's the one place
        # telemetry setup is guaranteed to happen exactly once, before any
        # app code that might create a span.
        from config.telemetry import configure_telemetry

        configure_telemetry()
