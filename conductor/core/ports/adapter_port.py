from abc import ABC, abstractmethod

from conductor.core.domain.task import ConductorTask


class AdapterPort(ABC):
    """Contract for channel adapters (Linear, Telegram, Slack, …).

    Adapters translate external events into ConductorTask (inbound) and push
    results back to the source platform (outbound). They must not contain any
    business logic — that belongs in the orchestrator.
    """

    @abstractmethod
    async def to_task(self, payload: dict) -> ConductorTask:  # type: ignore[type-arg]
        """Translate an external event payload → ConductorTask."""
        ...

    @abstractmethod
    async def from_task(self, task: ConductorTask) -> None:
        """Push the task result back to the external platform.

        Examples: update a Linear ticket status, post a Telegram message.
        """
        ...
