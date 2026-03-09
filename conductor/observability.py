"""OpenTelemetry tracing setup for Conductor.

Traces are exported via OTLP to any compatible backend.
Langfuse is the recommended backend — it accepts OTLP on port 4318
and provides an LLM-aware UI with cost tracking and prompt management.

Configuration (via environment variables):
    LANGFUSE_HOST            Base URL of your Langfuse instance
                             (e.g. https://langfuse.yourdomain.com)
    LANGFUSE_PUBLIC_KEY      pk-lf-...
    LANGFUSE_SECRET_KEY      sk-lf-...
    OTEL_EXPORTER_OTLP_ENDPOINT  Alternative OTLP endpoint (overrides Langfuse)

If none of these are set, tracing is a no-op (spans are created but not exported).
"""

import logging
import os
from base64 import b64encode

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

logger = logging.getLogger(__name__)

_provider: TracerProvider | None = None
# Exposed for testing — lets tests capture spans without a real backend
_test_exporter: InMemorySpanExporter | None = None


def setup_tracing(service_name: str = "conductor") -> None:
    """Initialise the global TracerProvider. Call once at app startup."""
    global _provider, _test_exporter

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)

    exporter = _build_exporter()
    if exporter is None:
        logger.info("Tracing: no OTLP endpoint configured — spans will not be exported")
    else:
        provider.add_span_processor(BatchSpanProcessor(exporter))
        logger.info("Tracing: exporting spans via OTLP")

    trace.set_tracer_provider(provider)
    _provider = provider


def get_tracer(name: str = "conductor") -> trace.Tracer:
    """Return a tracer. Always safe to call — returns a no-op tracer if not initialised."""
    return trace.get_tracer(name)


def _build_exporter() -> SpanExporter | None:
    """Build an OTLP exporter from env vars, or return None if not configured."""
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    # Explicit OTLP endpoint takes precedence
    explicit_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if explicit_endpoint:
        return OTLPSpanExporter(endpoint=f"{explicit_endpoint.rstrip('/')}/v1/traces")

    # Langfuse OTLP endpoint (Langfuse accepts traces at /api/public/otel)
    langfuse_host = os.getenv("LANGFUSE_HOST")
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY", "")

    if langfuse_host and public_key and secret_key:
        token = b64encode(f"{public_key}:{secret_key}".encode()).decode()
        return OTLPSpanExporter(
            endpoint=f"{langfuse_host.rstrip('/')}/api/public/otel/v1/traces",
            headers={"Authorization": f"Basic {token}"},
        )

    return None
