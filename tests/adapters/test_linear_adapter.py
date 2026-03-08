from unittest.mock import AsyncMock, MagicMock

import pytest

from conductor.adapters.linear.adapter import LinearAdapter
from conductor.core.domain.task import AgentType, ConductorTask, TaskStatus


def make_adapter() -> tuple[LinearAdapter, MagicMock]:
    client = MagicMock()
    client.add_comment = AsyncMock()
    client.update_state = AsyncMock()
    client.get_workflow_states = AsyncMock(
        return_value=[
            {"id": "s-todo", "name": "Todo", "type": "unstarted"},
            {"id": "s-inprog", "name": "In Progress", "type": "started"},
            {"id": "s-done", "name": "Done", "type": "completed"},
        ]
    )
    adapter = LinearAdapter(client=client, team_id="team-1")
    return adapter, client


WEBHOOK_PAYLOAD = {
    "data": {
        "id": "issue-abc",
        "title": "Fix the login bug",
        "description": "Users cannot log in with SSO.",
        "team": {"id": "team-1"},
        "state": {"id": "s-todo"},
    }
}


@pytest.mark.asyncio
async def test_to_task_maps_fields_correctly():
    adapter, _ = make_adapter()
    task = await adapter.to_task(WEBHOOK_PAYLOAD)

    assert task.external_id == "issue-abc"
    assert task.source == "linear"
    assert task.title == "Fix the login bug"
    assert task.spec == "Users cannot log in with SSO."
    assert task.status == TaskStatus.PENDING
    assert task.assigned_to == AgentType.ORCHESTRATOR
    assert task.metadata["team_id"] == "team-1"


@pytest.mark.asyncio
async def test_to_task_missing_description_defaults_to_empty():
    adapter, _ = make_adapter()
    payload = {"data": {"id": "x", "title": "T"}}
    task = await adapter.to_task(payload)
    assert task.spec == ""


@pytest.mark.asyncio
async def test_to_task_bare_issue_dict():
    """Supports bare issue dict (no 'data' envelope) for easier testing."""
    adapter, _ = make_adapter()
    task = await adapter.to_task({"id": "bare-1", "title": "Bare"})
    assert task.external_id == "bare-1"


@pytest.mark.asyncio
async def test_from_task_posts_comment_from_history():
    adapter, client = make_adapter()
    task = ConductorTask(
        id="t1",
        external_id="issue-abc",
        source="linear",
        title="T",
        spec="",
        status=TaskStatus.IN_PROGRESS_DEV,
        assigned_to=AgentType.DEVELOPER,
        history=[{"result": "I fixed it!", "from": "pending", "to": "in_progress_dev"}],
    )
    await adapter.from_task(task)
    client.add_comment.assert_awaited_once_with("issue-abc", "I fixed it!")


@pytest.mark.asyncio
async def test_from_task_fallback_comment_when_no_result():
    adapter, client = make_adapter()
    task = ConductorTask(
        id="t1",
        external_id="issue-abc",
        source="linear",
        title="T",
        spec="",
        status=TaskStatus.PENDING,
        assigned_to=AgentType.ORCHESTRATOR,
    )
    await adapter.from_task(task)
    call_args = client.add_comment.call_args[0]
    assert "pending" in call_args[1]


@pytest.mark.asyncio
async def test_from_task_updates_linear_state():
    adapter, client = make_adapter()
    task = ConductorTask(
        id="t1",
        external_id="issue-abc",
        source="linear",
        title="T",
        spec="",
        status=TaskStatus.DONE,
        assigned_to=AgentType.DEPLOYER,
    )
    await adapter.from_task(task)
    client.update_state.assert_awaited_once_with("issue-abc", "s-done")


@pytest.mark.asyncio
async def test_state_map_is_cached():
    """get_workflow_states should only be called once across multiple from_task calls."""
    adapter, client = make_adapter()

    async def make_task(status: TaskStatus) -> ConductorTask:
        return ConductorTask(
            id="t1",
            external_id="issue-abc",
            source="linear",
            title="T",
            spec="",
            status=status,
            assigned_to=AgentType.ORCHESTRATOR,
        )

    await adapter.from_task(await make_task(TaskStatus.PENDING))
    await adapter.from_task(await make_task(TaskStatus.DONE))

    assert client.get_workflow_states.await_count == 1
