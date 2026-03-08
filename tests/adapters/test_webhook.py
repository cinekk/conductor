"""Integration tests for the webhook endpoint."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

import conductor.api.webhook as webhook_module
from conductor.api.webhook import app
from conductor.core.domain.task import AgentType, ConductorTask, TaskStatus
from conductor.core.ports.adapter_port import AdapterPort


class DummyAdapter(AdapterPort):
    def __init__(self, task: ConductorTask) -> None:
        self._task = task
        self.published: list[ConductorTask] = []

    async def to_task(self, payload: dict) -> ConductorTask:  # type: ignore[type-arg]
        return self._task

    async def from_task(self, task: ConductorTask) -> None:
        self.published.append(task)


def make_task() -> ConductorTask:
    return ConductorTask(
        id=str(uuid.uuid4()),
        external_id="LIN-1",
        source="linear",
        title="Test",
        spec="spec",
        status=TaskStatus.PENDING,
        assigned_to=AgentType.ORCHESTRATOR,
    )


@pytest.fixture(autouse=True)
def reset_registries():
    """Ensure a clean registry state for every test."""
    original_adapters = webhook_module.adapter_registry.copy()
    original_orchestrator = webhook_module.orchestrator
    yield
    webhook_module.adapter_registry.clear()
    webhook_module.adapter_registry.update(original_adapters)
    webhook_module.orchestrator = original_orchestrator


def test_health_check():
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_unknown_source_returns_404():
    client = TestClient(app)
    resp = client.post("/webhook/unknown", json={"foo": "bar"})
    assert resp.status_code == 404


def test_known_source_returns_202_accepted():
    task = make_task()
    adapter = DummyAdapter(task)

    mock_orch = MagicMock()
    mock_orch.handle = AsyncMock(return_value=task)

    webhook_module.adapter_registry["linear"] = adapter
    webhook_module.orchestrator = mock_orch  # type: ignore[assignment]

    client = TestClient(app)
    resp = client.post("/webhook/linear", json={"action": "create"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "accepted"
