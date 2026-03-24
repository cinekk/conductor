"""Verify that Orchestrator.handle() emits OTEL spans with the right attributes."""

import uuid
from unittest.mock import patch

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from conductor.core.domain.task import AgentType, ConductorProject, ConductorTask, TaskStatus
from conductor.core.orchestrator import Orchestrator
from conductor.core.ports.agent_port import AgentPort


class EchoAgent(AgentPort):
    async def execute(self, task: ConductorTask) -> ConductorTask:
        return task


_PROJECT = ConductorProject(id="testapp", name="TestApp", repo_url="git@github.com:org/testapp.git")


def make_task() -> ConductorTask:
    return ConductorTask(
        id=str(uuid.uuid4()),
        external_id="LIN-42",
        source="linear",
        title="Test",
        spec="spec",
        status=TaskStatus.PENDING,
        assigned_to=AgentType.ORCHESTRATOR,
        project=_PROJECT,
    )


@pytest.fixture()
def span_collector():
    """Return (exporter, tracer) backed by an in-memory provider."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("test")
    return exporter, tracer


@pytest.mark.asyncio
async def test_handle_emits_task_and_agent_spans(span_collector):
    exporter, tracer = span_collector
    orch = Orchestrator(agent_registry={AgentType.ORCHESTRATOR: EchoAgent()})

    with patch("conductor.core.orchestrator.get_tracer", return_value=tracer):
        await orch.handle(make_task())

    spans = {s.name: s for s in exporter.get_finished_spans()}
    assert "task.handle" in spans
    assert "agent.execute:orchestrator" in spans


@pytest.mark.asyncio
async def test_task_span_carries_metadata(span_collector):
    exporter, tracer = span_collector
    task = make_task()
    orch = Orchestrator(agent_registry={AgentType.ORCHESTRATOR: EchoAgent()})

    with patch("conductor.core.orchestrator.get_tracer", return_value=tracer):
        await orch.handle(task)

    task_span = next(s for s in exporter.get_finished_spans() if s.name == "task.handle")
    assert task_span.attributes["task.id"] == task.id
    assert task_span.attributes["task.source"] == "linear"
    assert task_span.attributes["task.status"] == TaskStatus.PENDING.value
    assert task_span.attributes["task.agent_type"] == AgentType.ORCHESTRATOR.value


@pytest.mark.asyncio
async def test_agent_span_carries_result_status(span_collector):
    exporter, tracer = span_collector
    orch = Orchestrator(agent_registry={AgentType.ORCHESTRATOR: EchoAgent()})

    with patch("conductor.core.orchestrator.get_tracer", return_value=tracer):
        await orch.handle(make_task())

    agent_span = next(
        s for s in exporter.get_finished_spans() if s.name == "agent.execute:orchestrator"
    )
    assert agent_span.attributes["agent.result_status"] == TaskStatus.PENDING.value
