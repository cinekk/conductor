from conductor.core.domain.task import AgentType, ConductorTask, TaskStatus
from conductor.core.ports.agent_port import AgentPort

# Routes task status → the agent type responsible for the next step
_ROUTING_TABLE: dict[TaskStatus, AgentType] = {
    TaskStatus.PENDING: AgentType.ORCHESTRATOR,
    TaskStatus.IN_PROGRESS_DEV: AgentType.DEVELOPER,
    TaskStatus.IN_PROGRESS_QA: AgentType.QA,
    TaskStatus.READY_FOR_DEPLOY: AgentType.DEPLOYER,
}


class UnroutableTaskError(Exception):
    """Raised when no agent is registered for the task's current status."""


class Orchestrator:
    """Routes tasks to the appropriate agent based on the current task status.

    The Orchestrator knows nothing about Linear, Telegram, or Claude — only
    about ports. Inject concrete implementations via the agent_registry.
    """

    def __init__(self, agent_registry: dict[AgentType, AgentPort]) -> None:
        self._agents = agent_registry

    async def handle(self, task: ConductorTask) -> ConductorTask:
        """Determine the responsible agent, delegate, and return the updated task."""
        agent_type = self._route(task)
        agent = self._agents.get(agent_type)
        if agent is None:
            raise UnroutableTaskError(
                f"No agent registered for type {agent_type!r} "
                f"(task {task.id!r} in status {task.status!r})"
            )
        return await agent.execute(task)

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
