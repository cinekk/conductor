"""Tests for OpenTelemetry tracing setup."""

from unittest.mock import patch

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


def test_get_tracer_before_setup_returns_tracer():
    """get_tracer() is always safe to call even without setup_tracing()."""
    from conductor.observability import get_tracer

    t = get_tracer("test")
    assert t is not None


def test_setup_tracing_registers_provider():
    """setup_tracing() calls set_tracer_provider with a real TracerProvider."""
    from conductor.observability import setup_tracing

    with patch("conductor.observability.trace.set_tracer_provider") as mock_set:
        setup_tracing("test-conductor")

    mock_set.assert_called_once()
    provider_arg = mock_set.call_args[0][0]
    assert isinstance(provider_arg, TracerProvider)


def test_build_exporter_no_env_vars(monkeypatch):
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.delenv("LANGFUSE_HOST", raising=False)
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)

    from conductor.observability import _build_exporter

    assert _build_exporter() is None


def test_build_exporter_with_explicit_otlp(monkeypatch):
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
    monkeypatch.delenv("LANGFUSE_HOST", raising=False)

    from conductor.observability import _build_exporter

    exporter = _build_exporter()
    assert exporter is not None


def test_build_exporter_with_langfuse_env(monkeypatch):
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.setenv("LANGFUSE_HOST", "https://langfuse.example.com")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-test")

    from conductor.observability import _build_exporter

    exporter = _build_exporter()
    assert exporter is not None


def test_build_exporter_langfuse_partial_config_returns_none(monkeypatch):
    """Langfuse exporter requires all three vars; partial config → no-op."""
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.setenv("LANGFUSE_HOST", "https://langfuse.example.com")
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)

    from conductor.observability import _build_exporter

    assert _build_exporter() is None


def test_explicit_otlp_takes_precedence_over_langfuse(monkeypatch):
    """OTEL_EXPORTER_OTLP_ENDPOINT should win even when Langfuse vars are set."""
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://custom:4318")
    monkeypatch.setenv("LANGFUSE_HOST", "https://langfuse.example.com")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-test")

    from conductor.observability import _build_exporter

    exporter = _build_exporter()
    assert exporter is not None
    # Verify the endpoint is the explicit one, not Langfuse
    assert "custom" in str(exporter._endpoint)  # type: ignore[attr-defined]


def test_spans_recorded_via_in_memory_exporter():
    """Verify OTEL span recording works end-to-end using a local provider."""
    memory_exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(memory_exporter))

    # Use provider directly — avoids touching the global singleton
    tracer = provider.get_tracer("test")
    with tracer.start_as_current_span("my.span") as span:
        span.set_attribute("test.key", "hello")

    finished = memory_exporter.get_finished_spans()
    assert len(finished) == 1
    assert finished[0].name == "my.span"
    assert finished[0].attributes["test.key"] == "hello"
