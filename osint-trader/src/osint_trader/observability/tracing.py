"""OpenTelemetry tracing helpers.

Tracing is opt-in: install `opentelemetry-sdk` + an exporter and set
`OTEL_EXPORTER_OTLP_ENDPOINT`. Without that, every `span()` is a cheap no-op
context manager so the rest of the code can stay decorated without runtime
penalty.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any

try:
    from opentelemetry import trace as _otel
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.resources import Resource
    _AVAILABLE = True
except ImportError:  # pragma: no cover - optional dep
    _otel = None
    _AVAILABLE = False

_INITIALISED = False


def init(service_name: str = "osint-trader") -> None:
    global _INITIALISED
    if _INITIALISED or not _AVAILABLE:
        return
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        return  # tracing disabled until the user opts in
    try:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    except ImportError:
        return

    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces")))
    _otel.set_tracer_provider(provider)
    _INITIALISED = True


@contextmanager
def span(name: str, **attrs: Any):
    if not _AVAILABLE or not _INITIALISED:
        yield None
        return
    tracer = _otel.get_tracer("osint-trader")
    with tracer.start_as_current_span(name) as s:
        for k, v in attrs.items():
            try:
                s.set_attribute(k, v)
            except Exception:
                pass
        yield s
