import uuid

from conductor.adapters.linear.client import LinearClient
from conductor.core.domain.task import AgentType, ConductorTask, TaskStatus
from conductor.core.ports.adapter_port import AdapterPort
from conductor.core.ports.project_registry_port import ProjectRegistryPort

# Maps internal TaskStatus values to Linear workflow state names.
# Linear state names are team-configurable, so we match by name (case-insensitive).
# Falls back gracefully if a state name doesn't exist in the team.
_STATUS_TO_LINEAR_STATE: dict[TaskStatus, str] = {
    TaskStatus.PENDING: "Todo",
    TaskStatus.IN_PROGRESS_DEV: "In Progress",
    TaskStatus.IN_PROGRESS_QA: "In Review",
    TaskStatus.NEEDS_WORK: "In Progress",
    TaskStatus.READY_FOR_DEPLOY: "In Review",
    TaskStatus.DEPLOYING: "In Progress",
    TaskStatus.UAT: "In Review",
    TaskStatus.DONE: "Done",
}


class LinearAdapter(AdapterPort):
    """AdapterPort implementation for Linear webhooks.

    Inbound:  IssueCreate / IssueUpdate webhook payload → ConductorTask
    Outbound: ConductorTask result → Linear comment + optional state update
    """

    def __init__(
        self,
        client: LinearClient,
        team_id: str,
        project_registry: ProjectRegistryPort | None = None,
    ) -> None:
        self._client = client
        self._team_id = team_id
        self._registry = project_registry
        # Lazy-loaded state map: {name_lower: state_id}
        self._state_map: dict[str, str] = {}

    async def to_task(self, payload: dict) -> ConductorTask:  # type: ignore[type-arg]
        """Translate a Linear webhook payload into a ConductorTask.

        Supports both `data` envelope (webhook format) and bare issue dicts
        (for easier testing).
        """
        issue = payload.get("data", payload)
        project = None
        if self._registry is not None:
            linear_project_id = (issue.get("project") or {}).get("id")
            if linear_project_id:
                project = self._registry.get_by_integration_id("linear", linear_project_id)
        return ConductorTask(
            id=str(uuid.uuid4()),
            external_id=issue["id"],
            source="linear",
            title=issue["title"],
            spec=issue.get("description") or "",
            status=TaskStatus.PENDING,
            assigned_to=AgentType.ORCHESTRATOR,
            project=project,
            metadata={
                "team_id": (issue.get("team") or {}).get("id", self._team_id),
                "state_id": (issue.get("state") or {}).get("id"),
            },
        )

    async def from_task(self, task: ConductorTask) -> None:
        """Post the agent result as a Linear comment and update the issue state."""
        comment = self._build_comment(task)
        await self._client.add_comment(task.external_id, comment)
        await self._maybe_update_state(task)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_comment(self, task: ConductorTask) -> str:
        last = task.history[-1] if task.history else {}
        result = last.get("result")
        if result:
            return str(result)
        return f"Task moved to `{task.status}`."

    async def _maybe_update_state(self, task: ConductorTask) -> None:
        linear_state_name = _STATUS_TO_LINEAR_STATE.get(task.status)
        if not linear_state_name:
            return
        state_id = await self._resolve_state_id(linear_state_name)
        if state_id:
            await self._client.update_state(task.external_id, state_id)

    async def _resolve_state_id(self, state_name: str) -> str | None:
        """Look up a Linear state ID by name, with lazy caching."""
        if not self._state_map:
            states = await self._client.get_workflow_states(self._team_id)
            self._state_map = {s["name"].lower(): s["id"] for s in states}
        return self._state_map.get(state_name.lower())
