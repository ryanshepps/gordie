"""Tracing initialization via Logfire with auto-instrumentation."""

import os
from contextlib import contextmanager
from typing import Any

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

_initialized = False

SERVICE_NAME = "fantasy-agent"
SERVICE_VERSION = "0.1.0"

# Application packages to auto-trace.
# install_auto_tracing() rewrites these at import time,
# so init() MUST be called before they are imported.
_AUTO_TRACE_PACKAGES = [
    "agent",
    "client",
    "data",
    "middleware",
    "scheduled",
    "server",
    "tools",
]


def init() -> None:
    """
    Initialize Logfire tracing with auto-instrumentation.

    MUST be called before importing any application packages
    (agent, client, data, middleware, scheduled, server, tools).

    Safe to call multiple times — subsequent calls are no-ops.
    """
    global _initialized
    if _initialized:
        return

    import logfire

    environment = os.getenv("ENVIRONMENT", "development")

    # Set the OTLP endpoint for Tempo if not already configured.
    # Logfire uses HTTP/protobuf (port 4318), not gRPC (4317).
    os.environ.setdefault("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
    os.environ.setdefault("OTEL_METRICS_EXPORTER", "none")

    logfire.configure(
        service_name=SERVICE_NAME,
        service_version=SERVICE_VERSION,
        send_to_logfire=False,
        environment=environment,
    )

    logfire.install_auto_tracing(
        modules=_AUTO_TRACE_PACKAGES,
        min_duration=0,
    )

    _initialized = True


@contextmanager
def create_span(
    name: str,
    attributes: dict[str, Any] | None = None,
    tracer_name: str | None = None,
):
    """
    Create a new span as a context manager.

    Args:
        name: Span name
        attributes: Optional span attributes
        tracer_name: Optional tracer name

    Yields:
        The created span
    """
    tracer = trace.get_tracer(tracer_name or SERVICE_NAME)
    with tracer.start_as_current_span(name, attributes=attributes) as span:
        yield span


def record_exception(span: trace.Span, exception: Exception) -> None:
    """Record an exception on a span and set error status."""
    span.record_exception(exception)
    span.set_status(Status(StatusCode.ERROR, str(exception)))


def set_span_ok(span: trace.Span) -> None:
    """Set span status to OK."""
    span.set_status(Status(StatusCode.OK))


def get_current_span() -> trace.Span:
    """Get the current active span."""
    return trace.get_current_span()
