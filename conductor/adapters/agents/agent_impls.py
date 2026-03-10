"""Concrete AgentPort implementations for each AgentType.

Each agent:
  1. Fetches its system prompt from the PromptRegistry.
  2. Calls the LLM with the task spec as the user prompt.
  3. Appends the LLM result to the task history.
  4. Transitions the task to the appropriate next status.

Tool allowlists per agent type (mirrors comments in claude_agent.py):
  OrchestratorAgent → Read
  DeveloperAgent    → Read, Write, Edit, Bash
  QAAgent           → Read, Bash
  DeployerAgent     → Read, Bash
  ResearcherAgent   → Read
"""

from __future__ import annotations

from datetime import UTC, datetime

from conductor.core.domain.task import AgentType, ConductorTask, TaskStatus
from conductor.core.ports.agent_port import AgentPort
from conductor.core.ports.llm_port import LLMPort
from conductor.prompts import PromptRegistry


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()


def _user_prompt(task: ConductorTask) -> str:
    return f"Title: {task.title}\n\nSpec:\n{task.spec}"


class OrchestratorAgent(AgentPort):
    """Analyses a PENDING task and hands it off to the developer."""

    _TOOLS: list[str] = ["Read"]
    _PROMPT_NAME = "orchestrator-agent"

    def __init__(self, llm: LLMPort, prompts: PromptRegistry) -> None:
        self._llm = llm
        self._prompts = prompts

    async def execute(self, task: ConductorTask) -> ConductorTask:
        system_prompt = self._prompts.get(self._PROMPT_NAME, spec=task.spec)
        result = await self._llm.run(system_prompt, _user_prompt(task), self._TOOLS)
        task.history.append(
            {"agent": AgentType.ORCHESTRATOR.value, "result": result, "at": _utcnow_iso()}
        )
        task.transition(TaskStatus.IN_PROGRESS_DEV)
        task.assigned_to = AgentType.DEVELOPER
        return task


class DeveloperAgent(AgentPort):
    """Implements the task and passes it to QA."""

    _TOOLS: list[str] = ["Read", "Write", "Edit", "Bash"]
    _PROMPT_NAME = "developer-agent"

    def __init__(self, llm: LLMPort, prompts: PromptRegistry) -> None:
        self._llm = llm
        self._prompts = prompts

    async def execute(self, task: ConductorTask) -> ConductorTask:
        system_prompt = self._prompts.get(self._PROMPT_NAME, spec=task.spec)
        result = await self._llm.run(system_prompt, _user_prompt(task), self._TOOLS)
        task.history.append(
            {"agent": AgentType.DEVELOPER.value, "result": result, "at": _utcnow_iso()}
        )
        task.transition(TaskStatus.IN_PROGRESS_QA)
        task.assigned_to = AgentType.QA
        return task


class QAAgent(AgentPort):
    """Reviews the implementation and either approves or requests changes.

    If the LLM response contains the exact token ``NEEDS_WORK`` the task is
    sent back to the developer; otherwise it advances to READY_FOR_DEPLOY.
    """

    _TOOLS: list[str] = ["Read", "Bash"]
    _PROMPT_NAME = "qa-agent"
    _NEEDS_WORK_SIGNAL = "NEEDS_WORK"

    def __init__(self, llm: LLMPort, prompts: PromptRegistry) -> None:
        self._llm = llm
        self._prompts = prompts

    async def execute(self, task: ConductorTask) -> ConductorTask:
        system_prompt = self._prompts.get(self._PROMPT_NAME, spec=task.spec)
        result = await self._llm.run(system_prompt, _user_prompt(task), self._TOOLS)
        task.history.append({"agent": AgentType.QA.value, "result": result, "at": _utcnow_iso()})
        if self._NEEDS_WORK_SIGNAL in result:
            task.transition(TaskStatus.NEEDS_WORK)
            task.assigned_to = AgentType.DEVELOPER
        else:
            task.transition(TaskStatus.READY_FOR_DEPLOY)
            task.assigned_to = AgentType.DEPLOYER
        return task


class DeployerAgent(AgentPort):
    """Deploys the approved implementation."""

    _TOOLS: list[str] = ["Read", "Bash"]
    _PROMPT_NAME = "deployer-agent"

    def __init__(self, llm: LLMPort, prompts: PromptRegistry) -> None:
        self._llm = llm
        self._prompts = prompts

    async def execute(self, task: ConductorTask) -> ConductorTask:
        system_prompt = self._prompts.get(self._PROMPT_NAME, spec=task.spec)
        result = await self._llm.run(system_prompt, _user_prompt(task), self._TOOLS)
        task.history.append(
            {"agent": AgentType.DEPLOYER.value, "result": result, "at": _utcnow_iso()}
        )
        task.transition(TaskStatus.DEPLOYING)
        return task


class ResearcherAgent(AgentPort):
    """Gathers information and produces a report without advancing the task status."""

    _TOOLS: list[str] = ["Read"]
    _PROMPT_NAME = "researcher-agent"

    def __init__(self, llm: LLMPort, prompts: PromptRegistry) -> None:
        self._llm = llm
        self._prompts = prompts

    async def execute(self, task: ConductorTask) -> ConductorTask:
        system_prompt = self._prompts.get(self._PROMPT_NAME, spec=task.spec)
        result = await self._llm.run(system_prompt, _user_prompt(task), self._TOOLS)
        task.history.append(
            {"agent": AgentType.RESEARCHER.value, "result": result, "at": _utcnow_iso()}
        )
        return task
