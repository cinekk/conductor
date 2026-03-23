"""Tests for concrete AgentPort implementations (M3)."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from conductor.adapters.agents.agent_impls import (
    DeployerAgent,
    DeveloperAgent,
    OrchestratorAgent,
    QAAgent,
    ResearcherAgent,
)
from conductor.core.domain.task import AgentType, ConductorTask, TaskStatus
from conductor.core.ports.llm_port import LLMPort
from conductor.prompts import PromptRegistry


class _MockLLM(LLMPort):
    """Minimal in-test stub — avoids importing claude_agent_sdk."""

    def __init__(self, response: str = "mock response") -> None:
        self._response = response

    async def run(
        self,
        system_prompt: str,
        user_prompt: str,
        tools: list[str] | None = None,
    ) -> str:
        return self._response


# Alias to keep test body readable
MockLLMAdapter = _MockLLM


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def prompts(tmp_path: Path) -> PromptRegistry:
    """Minimal prompt registry with one version per agent prompt."""
    d = tmp_path / "prompt_templates"
    d.mkdir()
    (d / "orchestrator-agent@1.txt").write_text("orchestrate: {spec}", encoding="utf-8")
    (d / "developer-agent@1.txt").write_text("develop: {spec}", encoding="utf-8")
    (d / "qa-agent@1.txt").write_text("qa: {spec}", encoding="utf-8")
    (d / "deployer-agent@1.txt").write_text("deploy: {spec}", encoding="utf-8")
    (d / "researcher-agent@1.txt").write_text("research: {spec}", encoding="utf-8")
    return PromptRegistry(d)


def make_task(status: TaskStatus, agent: AgentType = AgentType.ORCHESTRATOR) -> ConductorTask:
    return ConductorTask(
        id=str(uuid.uuid4()),
        external_id="LIN-42",
        source="linear",
        title="Test task",
        spec="Implement X",
        status=status,
        assigned_to=agent,
    )


# ---------------------------------------------------------------------------
# OrchestratorAgent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_orchestrator_transitions_to_in_progress_dev(prompts: PromptRegistry) -> None:
    agent = OrchestratorAgent(llm=MockLLMAdapter(response="task understood"), prompts=prompts)
    task = make_task(TaskStatus.PENDING)
    result = await agent.execute(task)
    assert result.status == TaskStatus.IN_PROGRESS_DEV


@pytest.mark.asyncio
async def test_orchestrator_assigns_developer(prompts: PromptRegistry) -> None:
    agent = OrchestratorAgent(llm=MockLLMAdapter(), prompts=prompts)
    task = make_task(TaskStatus.PENDING)
    result = await agent.execute(task)
    assert result.assigned_to == AgentType.DEVELOPER


@pytest.mark.asyncio
async def test_orchestrator_appends_history(prompts: PromptRegistry) -> None:
    agent = OrchestratorAgent(llm=MockLLMAdapter(response="ok"), prompts=prompts)
    task = make_task(TaskStatus.PENDING)
    result = await agent.execute(task)
    # history has the LLM result entry plus the transition entry
    agent_entries = [e for e in result.history if e.get("agent") == AgentType.ORCHESTRATOR.value]
    assert len(agent_entries) == 1
    assert agent_entries[0]["result"] == "ok"


# ---------------------------------------------------------------------------
# DeveloperAgent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_developer_transitions_to_in_progress_qa(prompts: PromptRegistry) -> None:
    agent = DeveloperAgent(llm=MockLLMAdapter(response="done"), prompts=prompts)
    task = make_task(TaskStatus.IN_PROGRESS_DEV, AgentType.DEVELOPER)
    result = await agent.execute(task)
    assert result.status == TaskStatus.IN_PROGRESS_QA


@pytest.mark.asyncio
async def test_developer_assigns_qa(prompts: PromptRegistry) -> None:
    agent = DeveloperAgent(llm=MockLLMAdapter(), prompts=prompts)
    task = make_task(TaskStatus.IN_PROGRESS_DEV, AgentType.DEVELOPER)
    result = await agent.execute(task)
    assert result.assigned_to == AgentType.QA


@pytest.mark.asyncio
async def test_developer_appends_history(prompts: PromptRegistry) -> None:
    agent = DeveloperAgent(llm=MockLLMAdapter(response="implemented"), prompts=prompts)
    task = make_task(TaskStatus.IN_PROGRESS_DEV, AgentType.DEVELOPER)
    result = await agent.execute(task)
    agent_entries = [e for e in result.history if e.get("agent") == AgentType.DEVELOPER.value]
    assert len(agent_entries) == 1
    assert agent_entries[0]["result"] == "implemented"


# ---------------------------------------------------------------------------
# QAAgent — approval path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_qa_approves_when_no_needs_work_signal(prompts: PromptRegistry) -> None:
    agent = QAAgent(llm=MockLLMAdapter(response="All tests pass. Approved."), prompts=prompts)
    task = make_task(TaskStatus.IN_PROGRESS_QA, AgentType.QA)
    result = await agent.execute(task)
    assert result.status == TaskStatus.READY_FOR_DEPLOY


@pytest.mark.asyncio
async def test_qa_assigns_deployer_on_approval(prompts: PromptRegistry) -> None:
    agent = QAAgent(llm=MockLLMAdapter(response="Approved."), prompts=prompts)
    task = make_task(TaskStatus.IN_PROGRESS_QA, AgentType.QA)
    result = await agent.execute(task)
    assert result.assigned_to == AgentType.DEPLOYER


# ---------------------------------------------------------------------------
# QAAgent — rejection path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_qa_requests_changes_when_needs_work_signal_present(
    prompts: PromptRegistry,
) -> None:
    agent = QAAgent(
        llm=MockLLMAdapter(response="NEEDS_WORK\nFix the null pointer in handler."),
        prompts=prompts,
    )
    task = make_task(TaskStatus.IN_PROGRESS_QA, AgentType.QA)
    result = await agent.execute(task)
    assert result.status == TaskStatus.NEEDS_WORK


@pytest.mark.asyncio
async def test_qa_assigns_developer_on_needs_work(prompts: PromptRegistry) -> None:
    agent = QAAgent(llm=MockLLMAdapter(response="NEEDS_WORK"), prompts=prompts)
    task = make_task(TaskStatus.IN_PROGRESS_QA, AgentType.QA)
    result = await agent.execute(task)
    assert result.assigned_to == AgentType.DEVELOPER


@pytest.mark.asyncio
async def test_qa_appends_history(prompts: PromptRegistry) -> None:
    response = "NEEDS_WORK\nIssues found."
    agent = QAAgent(llm=MockLLMAdapter(response=response), prompts=prompts)
    task = make_task(TaskStatus.IN_PROGRESS_QA, AgentType.QA)
    result = await agent.execute(task)
    agent_entries = [e for e in result.history if e.get("agent") == AgentType.QA.value]
    assert len(agent_entries) == 1
    assert agent_entries[0]["result"] == response


# ---------------------------------------------------------------------------
# DeployerAgent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deployer_transitions_to_deploying(prompts: PromptRegistry) -> None:
    agent = DeployerAgent(llm=MockLLMAdapter(response="deployed"), prompts=prompts)
    task = make_task(TaskStatus.READY_FOR_DEPLOY, AgentType.DEPLOYER)
    result = await agent.execute(task)
    assert result.status == TaskStatus.DEPLOYING


@pytest.mark.asyncio
async def test_deployer_appends_history(prompts: PromptRegistry) -> None:
    agent = DeployerAgent(llm=MockLLMAdapter(response="deployed v1.2"), prompts=prompts)
    task = make_task(TaskStatus.READY_FOR_DEPLOY, AgentType.DEPLOYER)
    result = await agent.execute(task)
    agent_entries = [e for e in result.history if e.get("agent") == AgentType.DEPLOYER.value]
    assert len(agent_entries) == 1
    assert agent_entries[0]["result"] == "deployed v1.2"


# ---------------------------------------------------------------------------
# ResearcherAgent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_researcher_does_not_change_status(prompts: PromptRegistry) -> None:
    """Researcher only records findings; it never transitions the task."""
    agent = ResearcherAgent(llm=MockLLMAdapter(response="findings"), prompts=prompts)
    task = make_task(TaskStatus.PENDING)
    original_status = task.status
    result = await agent.execute(task)
    assert result.status == original_status


@pytest.mark.asyncio
async def test_researcher_appends_history(prompts: PromptRegistry) -> None:
    agent = ResearcherAgent(llm=MockLLMAdapter(response="report text"), prompts=prompts)
    task = make_task(TaskStatus.PENDING)
    result = await agent.execute(task)
    agent_entries = [e for e in result.history if e.get("agent") == AgentType.RESEARCHER.value]
    assert len(agent_entries) == 1
    assert agent_entries[0]["result"] == "report text"


# ---------------------------------------------------------------------------
# Smoke test: real prompt templates load correctly for each agent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_all_agents_use_real_prompt_templates() -> None:
    """Ensure each agent can fetch its prompt from the real template directory."""
    real_prompts = PromptRegistry()

    async def _run(agent_cls: type, status: TaskStatus, agent_type: AgentType) -> None:
        agent = agent_cls(llm=MockLLMAdapter(), prompts=real_prompts)
        task = make_task(status, agent_type)
        await agent.execute(task)  # should not raise PromptNotFoundError

    # Orchestrator and Researcher don't need valid status transitions for this check
    # so we use statuses that each agent is designed to handle.
    await _run(OrchestratorAgent, TaskStatus.PENDING, AgentType.ORCHESTRATOR)
    await _run(DeveloperAgent, TaskStatus.IN_PROGRESS_DEV, AgentType.DEVELOPER)
    await _run(QAAgent, TaskStatus.IN_PROGRESS_QA, AgentType.QA)
    await _run(DeployerAgent, TaskStatus.READY_FOR_DEPLOY, AgentType.DEPLOYER)
