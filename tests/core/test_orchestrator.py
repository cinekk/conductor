import uuid

import pytest

from conductor.core.domain.task import AgentType, ConductorProject, ConductorTask, MissingProjectError, TaskStatus
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


_SAMPLE_PROJECT = ConductorProject(
    id="myapp",
    name="MyApp",
    repo_url="git@github.com:org/myapp.git",
)


def make_task(
    status: TaskStatus,
    agent: AgentType = AgentType.ORCHESTRATOR,
    project: ConductorProject | None = None,
) -> ConductorTask:
    return ConductorTask(
        id=str(uuid.uuid4()),
        external_id="LIN-1",
        source="linear",
        title="Test",
        spec="spec",
        status=status,
        assigned_to=agent,
        project=project,
    )


def make_orchestrator() -> Orchestrator:
    return Orchestrator(
        agent_registry={
            AgentType.ORCHESTRATOR: EchoAgent(),
            AgentType.DEVELOPER: TransitioningAgent(TaskStatus.IN_PROGRESS_QA),
            AgentType.QA: TransitioningAgent(TaskStatus.READY_FOR_DEPLOY),
            AgentType.DEPLOYER: TransitioningAgent(TaskStatus.DEPLOYING),
            AgentType.RESEARCHER: EchoAgent(),
        }
    )


@pytest.mark.asyncio
async def test_routes_pending_to_orchestrator():
    orch = make_orchestrator()
    task = make_task(TaskStatus.PENDING, project=_SAMPLE_PROJECT)
    result = await orch.handle(task)
    assert result.status == TaskStatus.PENDING  # EchoAgent leaves it unchanged


@pytest.mark.asyncio
async def test_routes_in_progress_dev_to_developer():
    orch = make_orchestrator()
    task = make_task(TaskStatus.IN_PROGRESS_DEV, project=_SAMPLE_PROJECT)
    result = await orch.handle(task)
    assert result.status == TaskStatus.IN_PROGRESS_QA


@pytest.mark.asyncio
async def test_routes_in_progress_qa_to_qa():
    orch = make_orchestrator()
    task = make_task(TaskStatus.IN_PROGRESS_QA, project=_SAMPLE_PROJECT)
    result = await orch.handle(task)
    assert result.status == TaskStatus.READY_FOR_DEPLOY


@pytest.mark.asyncio
async def test_routes_ready_for_deploy_to_deployer():
    orch = make_orchestrator()
    task = make_task(TaskStatus.READY_FOR_DEPLOY, project=_SAMPLE_PROJECT)
    result = await orch.handle(task)
    assert result.status == TaskStatus.DEPLOYING


@pytest.mark.asyncio
async def test_unroutable_status_raises():
    orch = make_orchestrator()
    task = make_task(TaskStatus.DONE, project=_SAMPLE_PROJECT)
    with pytest.raises(UnroutableTaskError, match="done"):
        await orch.handle(task)


@pytest.mark.asyncio
async def test_missing_agent_raises():
    orch = Orchestrator(agent_registry={})  # empty registry
    task = make_task(TaskStatus.PENDING, project=_SAMPLE_PROJECT)
    with pytest.raises(UnroutableTaskError, match="No agent registered"):
        await orch.handle(task)


# ---------------------------------------------------------------------------
# Project-based routing tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_routes_to_researcher_when_project_is_none():
    """Tasks with no project context must go to RESEARCHER regardless of status."""
    orch = make_orchestrator()
    task = make_task(TaskStatus.PENDING, project=None)
    result = await orch.handle(task)
    # EchoAgent leaves status unchanged
    assert result.status == TaskStatus.PENDING


@pytest.mark.asyncio
async def test_researcher_not_registered_raises_when_project_is_none():
    orch = Orchestrator(
        agent_registry={
            AgentType.ORCHESTRATOR: EchoAgent(),
        }
    )
    task = make_task(TaskStatus.PENDING, project=None)
    with pytest.raises(UnroutableTaskError, match="RESEARCHER"):
        await orch.handle(task)


@pytest.mark.asyncio
async def test_full_pipeline_used_when_project_is_set():
    """Tasks with a project set use the normal routing table (PENDING → ORCHESTRATOR)."""
    orch = make_orchestrator()
    task = make_task(TaskStatus.PENDING, project=_SAMPLE_PROJECT)
    result = await orch.handle(task)
    assert result.status == TaskStatus.PENDING  # ORCHESTRATOR → EchoAgent


@pytest.mark.asyncio
async def test_require_project_raises_missing_project_error():
    task = make_task(TaskStatus.IN_PROGRESS_DEV, project=None)
    with pytest.raises(MissingProjectError, match="no project configured"):
        Orchestrator._require_project(task)


def test_require_project_returns_project_when_set():
    task = make_task(TaskStatus.IN_PROGRESS_DEV, project=_SAMPLE_PROJECT)
    project = Orchestrator._require_project(task)
    assert project.id == "myapp"
