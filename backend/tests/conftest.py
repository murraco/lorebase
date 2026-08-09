from collections.abc import Callable, Iterator

import pymupdf
import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


@pytest.fixture
def make_pdf_bytes() -> Callable[[list[tuple[str, str]]], bytes]:
    """Factory fixture: build a minimal real PDF, one page per (heading,
    body) pair, using a font-size step-down so pymupdf4llm infers a
    heading + body paragraph per page — verified against the real library
    output, not assumed.
    """

    def _make(pages: list[tuple[str, str]]) -> bytes:
        doc = pymupdf.open()
        for heading, body in pages:
            page = doc.new_page()
            page.insert_text((72, 72), heading, fontsize=20)
            page.insert_text((72, 110), body, fontsize=11)
        pdf_bytes = doc.tobytes()
        doc.close()
        return pdf_bytes

    return _make


@pytest.fixture
def otel_spans() -> Iterator[InMemorySpanExporter]:
    """The real TracerProvider (config.telemetry.configure_telemetry(),
    run once via core.apps.CoreConfig.ready()) has no exporter attached in
    tests — OTEL_EXPORTER_OTLP_ENDPOINT is never set here, on purpose, so
    no test ever tries to reach a network. This adds an in-memory one just
    for the duration of a test, onto that same real provider, rather than
    replacing it: the OTel API only lets the global provider be set once
    per process, so a test can't swap in its own from scratch.
    """
    provider = trace.get_tracer_provider()
    assert isinstance(provider, TracerProvider), (
        "expected core.apps.CoreConfig.ready() to have installed a real SDK "
        "TracerProvider by the time tests run"
    )
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    yield exporter
    exporter.clear()
