from abc import ABC, abstractmethod

from conductor.core.domain.task import ConductorTask


class AgentPort(ABC):
    """Contract for all agents that execute tasks.

    Agents receive a ConductorTask, do their work, and return the updated task
    with results appended to the history. They must not interact with external
    platforms directly — that's the adapter's responsibility.
    """

    @abstractmethod
    async def execute(self, task: ConductorTask) -> ConductorTask:
        """Execute the task and return the updated task with results in history."""
        ...
