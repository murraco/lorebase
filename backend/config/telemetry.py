"""OpenTelemetry setup for the ingestion pipeline and the query path.

Configured entirely through the SDK's own standard environment variables
(`OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_EXPORTER_OTLP_HEADERS`,
`OTEL_SERVICE_NAME`) rather than project-specific settings — anyone who
already knows OpenTelemetry recognizes these names, and `OTLPSpanExporter()`
reads them itself with zero code here. This deliberately has no idea
Langfuse exists: it exports generic OTLP, and which backend receives it
is entirely a matter of what `OTEL_EXPORTER_OTLP_ENDPOINT` points at.

Spans are always created (see rag/retrieval/tracing.py and the ingestion
pipeline); whether they go anywhere depends only on whether
OTEL_EXPORTER_OTLP_ENDPOINT is set. Unset — the default, and what every
test run uses — this is a real no-op: no exporter gets attached, so
creating a span costs an object allocation and nothing ever tries to
reach the network.
"""

import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

_configured = False


def configure_telemetry() -> None:
    """Idempotent: AppConfig.ready() can run more than once per process
    in some management-command paths, and this must not attach a second
    exporter each time.
    """
    global _configured
    if _configured:
        return
    _configured = True

    service_name = os.environ.get("OTEL_SERVICE_NAME", "lorebase-backend")
    provider = TracerProvider(resource=Resource.create({SERVICE_NAME: service_name}))

    if os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))

    trace.set_tracer_provider(provider)
