"""OpenTelemetry tracing for the fantasy-agent application."""

import os
from contextlib import contextmanager
from typing import Any

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Status, StatusCode

# Global tracer provider
_tracer_provider: TracerProvider | None = None

# Service configuration
SERVICE_NAME = "fantasy-agent"
SERVICE_VERSION = "0.1.0"


def init_tracing(
    endpoint: str | None = None,
    environment: str | None = None,
) -> TracerProvider:
    """
    Initialize OpenTelemetry tracing with OTLP exporter.

    Args:
        endpoint: OTLP gRPC endpoint (default: localhost:4317)
        environment: Deployment environment (default: from ENVIRONMENT env var or "development")

    Returns:
        Configured TracerProvider
    """
    global _tracer_provider

    if _tracer_provider is not None:
        return _tracer_provider

    endpoint = endpoint or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "localhost:4317")
    environment = environment or os.getenv("ENVIRONMENT", "development")

    resource = Resource.create({
        "service.name": SERVICE_NAME,
        "service.version": SERVICE_VERSION,
        "deployment.environment": environment,
    })

    _tracer_provider = TracerProvider(resource=resource)

    otlp_exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
    span_processor = BatchSpanProcessor(otlp_exporter)
    _tracer_provider.add_span_processor(span_processor)

    trace.set_tracer_provider(_tracer_provider)

    return _tracer_provider


def get_tracer(name: str | None = None) -> trace.Tracer:
    """
    Get a tracer instance.

    Args:
        name: Tracer name (defaults to service name)

    Returns:
        Tracer instance
    """
    if _tracer_provider is None:
        init_tracing()

    return trace.get_tracer(name or SERVICE_NAME)


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

    Example:
        with create_span("agent.controller", {"user_email": "test@example.com"}) as span:
            # Do work
            span.add_event("processing_started")
    """
    tracer = get_tracer(tracer_name)
    with tracer.start_as_current_span(name, attributes=attributes) as span:
        yield span


def record_exception(span: trace.Span, exception: Exception) -> None:
    """
    Record an exception on a span and set error status.

    Args:
        span: The span to record the exception on
        exception: The exception to record
    """
    span.record_exception(exception)
    span.set_status(Status(StatusCode.ERROR, str(exception)))


def set_span_ok(span: trace.Span) -> None:
    """
    Set span status to OK.

    Args:
        span: The span to set status on
    """
    span.set_status(Status(StatusCode.OK))


def get_current_span() -> trace.Span:
    """
    Get the current active span.

    Returns:
        Current span (may be a no-op span if none is active)
    """
    return trace.get_current_span()
