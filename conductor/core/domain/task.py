from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


def _utcnow() -> datetime:
    return datetime.now(UTC)


class TaskStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS_DEV = "in_progress_dev"
    IN_PROGRESS_QA = "in_progress_qa"
    NEEDS_WORK = "needs_work"
    READY_FOR_DEPLOY = "ready_for_deploy"
    DEPLOYING = "deploying"
    UAT = "uat"
    DONE = "done"


# Valid transitions from each status
VALID_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.PENDING: {TaskStatus.IN_PROGRESS_DEV},
    TaskStatus.IN_PROGRESS_DEV: {TaskStatus.IN_PROGRESS_QA, TaskStatus.NEEDS_WORK},
    TaskStatus.IN_PROGRESS_QA: {TaskStatus.READY_FOR_DEPLOY, TaskStatus.NEEDS_WORK},
    TaskStatus.NEEDS_WORK: {TaskStatus.IN_PROGRESS_DEV},
    TaskStatus.READY_FOR_DEPLOY: {TaskStatus.DEPLOYING},
    TaskStatus.DEPLOYING: {TaskStatus.UAT, TaskStatus.NEEDS_WORK},
    TaskStatus.UAT: {TaskStatus.DONE, TaskStatus.NEEDS_WORK},
    TaskStatus.DONE: set(),
}


class AgentType(StrEnum):
    ORCHESTRATOR = "orchestrator"
    DEVELOPER = "developer"
    QA = "qa"
    DEPLOYER = "deployer"
    RESEARCHER = "researcher"


@dataclass
class ConductorTask:
    id: str                           # Internal UUID
    external_id: str                  # e.g. Linear issue ID
    source: str                       # e.g. "linear", "telegram"
    title: str
    spec: str                         # Full description / requirements
    status: TaskStatus
    assigned_to: AgentType
    history: list[dict[str, Any]] = field(default_factory=list)   # audit trail
    metadata: dict[str, Any] = field(default_factory=dict)        # source-specific extras
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)

    def transition(self, new_status: TaskStatus) -> None:
        """Transition to a new status, raising ValueError if the transition is invalid."""
        allowed = VALID_TRANSITIONS.get(self.status, set())
        if new_status not in allowed:
            raise ValueError(
                f"Cannot transition from {self.status!r} to {new_status!r}. "
                f"Allowed: {sorted(s.value for s in allowed) or 'none (terminal state)'}"
            )
        self.history.append(
            {
                "from": self.status.value,
                "to": new_status.value,
                "at": _utcnow().isoformat(),
            }
        )
        self.status = new_status
        self.updated_at = _utcnow()
