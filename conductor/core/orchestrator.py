from conductor.core.domain.task import (
    AgentType,
    ConductorProject,
    ConductorTask,
    MissingProjectError,
    TaskStatus,
)
from conductor.core.ports.agent_port import AgentPort
from conductor.observability import get_tracer

# Routes task status → the agent type responsible for the next step
_ROUTING_TABLE: dict[TaskStatus, AgentType] = {
    TaskStatus.PENDING: AgentType.ORCHESTRATOR,
    TaskStatus.IN_PROGRESS_DEV: AgentType.DEVELOPER,
    TaskStatus.IN_PROGRESS_QA: AgentType.QA,
    TaskStatus.READY_FOR_DEPLOY: AgentType.DEPLOYER,
}

# Agent types that operate on code and therefore require task.project to be set
_CODE_TOUCHING_AGENTS = {AgentType.DEVELOPER, AgentType.QA, AgentType.DEPLOYER}


class UnroutableTaskError(Exception):
    """Raised when no agent is registered for the task's current status."""


class Orchestrator:
    """Routes tasks to the appropriate agent based on the current task status.

    The Orchestrator knows nothing about Linear, Telegram, or Claude — only
    about ports. Inject concrete implementations via the agent_registry.

    Routing logic:
    - task.project is None → Researcher only (no repo context; research/Q&A only)
    - task.project is set  → full pipeline via _ROUTING_TABLE
    """

    def __init__(self, agent_registry: dict[AgentType, AgentPort]) -> None:
        self._agents = agent_registry

    async def handle(self, task: ConductorTask) -> ConductorTask:
        """Determine the responsible agent, delegate, and return the updated task."""
        tracer = get_tracer()
        with tracer.start_as_current_span("task.handle") as span:
            span.set_attribute("task.id", task.id)
            span.set_attribute("task.external_id", task.external_id)
            span.set_attribute("task.source", task.source)
            span.set_attribute("task.status", task.status.value)
            span.set_attribute("task.has_project", task.project is not None)

            if task.project is None:
                return await self._handle_no_project(task, span)

            agent_type = self._route(task)
            span.set_attribute("task.agent_type", agent_type.value)

            if agent_type in _CODE_TOUCHING_AGENTS:
                self._require_project(task)  # safety net — should never raise here

            agent = self._agents.get(agent_type)
            if agent is None:
                raise UnroutableTaskError(
                    f"No agent registered for type {agent_type!r} "
                    f"(task {task.id!r} in status {task.status!r})"
                )

            with tracer.start_as_current_span(f"agent.execute:{agent_type.value}") as agent_span:
                result = await agent.execute(task)
                agent_span.set_attribute("agent.result_status", result.status.value)
            return result

    async def _handle_no_project(self, task: ConductorTask, span: object) -> ConductorTask:
        """Route a project-less task to the Researcher agent."""
        if hasattr(span, "set_attribute"):
            span.set_attribute("task.agent_type", AgentType.RESEARCHER.value)  # type: ignore[union-attr]
        researcher = self._agents.get(AgentType.RESEARCHER)
        if researcher is None:
            raise UnroutableTaskError(
                f"No RESEARCHER agent registered — required for tasks with no project context "
                f"(task {task.id!r})"
            )
        tracer = get_tracer()
        with tracer.start_as_current_span(f"agent.execute:{AgentType.RESEARCHER.value}") as s:
            result = await researcher.execute(task)
            s.set_attribute("agent.result_status", result.status.value)
        return result

    def _route(self, task: ConductorTask) -> AgentType:
        """Map the task's current status to the next agent type."""
        agent_type = _ROUTING_TABLE.get(task.status)
        if agent_type is None:
            raise UnroutableTaskError(
                f"No routing rule for task status {task.status!r} "
                f"(task {task.id!r}). "
                f"Routable statuses: {sorted(s.value for s in _ROUTING_TABLE)}"
            )
        return agent_type

    @staticmethod
    def _require_project(task: ConductorTask) -> ConductorProject:
        """Assert that the task has a project set.

        This is a programming-error guard — the orchestrator should have already
        routed project-less tasks to the Researcher before reaching code-touching agents.
        """
        if task.project is None:
            raise MissingProjectError(
                f"Task {task.id!r} has no project configured. "
                "Ensure this task has a project assigned before routing to code-touching agents."
            )
        return task.project
