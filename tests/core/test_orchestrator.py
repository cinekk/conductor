import uuid

import pytest

from conductor.core.domain.task import AgentType, ConductorTask, TaskStatus
from conductor.core.orchestrator import Orchestrator, UnroutableTaskError
from conductor.core.ports.agent_port import AgentPort


class EchoAgent(AgentPort):
    """Returns the task unchanged — useful for routing tests."""

    async def execute(self, task: ConductorTask) -> ConductorTask:
        return task


class TransitioningAgent(AgentPort):
    """Transitions the task to a given status on execute."""

    def __init__(self, next_status: TaskStatus) -> None:
        self._next_status = next_status

    async def execute(self, task: ConductorTask) -> ConductorTask:
        task.transition(self._next_status)
        return task


def make_task(status: TaskStatus, agent: AgentType = AgentType.ORCHESTRATOR) -> ConductorTask:
    return ConductorTask(
        id=str(uuid.uuid4()),
        external_id="LIN-1",
        source="linear",
        title="Test",
        spec="spec",
        status=status,
        assigned_to=agent,
    )


def make_orchestrator() -> Orchestrator:
    return Orchestrator(
        agent_registry={
            AgentType.ORCHESTRATOR: EchoAgent(),
            AgentType.DEVELOPER: TransitioningAgent(TaskStatus.IN_PROGRESS_QA),
            AgentType.QA: TransitioningAgent(TaskStatus.READY_FOR_DEPLOY),
            AgentType.DEPLOYER: TransitioningAgent(TaskStatus.DEPLOYING),
        }
    )


@pytest.mark.asyncio
async def test_routes_pending_to_orchestrator():
    orch = make_orchestrator()
    task = make_task(TaskStatus.PENDING)
    result = await orch.handle(task)
    assert result.status == TaskStatus.PENDING  # EchoAgent leaves it unchanged


@pytest.mark.asyncio
async def test_routes_in_progress_dev_to_developer():
    orch = make_orchestrator()
    task = make_task(TaskStatus.IN_PROGRESS_DEV)
    result = await orch.handle(task)
    assert result.status == TaskStatus.IN_PROGRESS_QA


@pytest.mark.asyncio
async def test_routes_in_progress_qa_to_qa():
    orch = make_orchestrator()
    task = make_task(TaskStatus.IN_PROGRESS_QA)
    result = await orch.handle(task)
    assert result.status == TaskStatus.READY_FOR_DEPLOY


@pytest.mark.asyncio
async def test_routes_ready_for_deploy_to_deployer():
    orch = make_orchestrator()
    task = make_task(TaskStatus.READY_FOR_DEPLOY)
    result = await orch.handle(task)
    assert result.status == TaskStatus.DEPLOYING


@pytest.mark.asyncio
async def test_unroutable_status_raises():
    orch = make_orchestrator()
    task = make_task(TaskStatus.DONE)
    with pytest.raises(UnroutableTaskError, match="done"):
        await orch.handle(task)


@pytest.mark.asyncio
async def test_missing_agent_raises():
    orch = Orchestrator(agent_registry={})  # empty registry
    task = make_task(TaskStatus.PENDING)
    with pytest.raises(UnroutableTaskError, match="No agent registered"):
        await orch.handle(task)
