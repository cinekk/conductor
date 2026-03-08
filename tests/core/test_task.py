import uuid

import pytest

from conductor.core.domain.task import AgentType, ConductorTask, TaskStatus


def make_task(**kwargs) -> ConductorTask:
    defaults = dict(
        id=str(uuid.uuid4()),
        external_id="LIN-1",
        source="linear",
        title="Test task",
        spec="Do the thing",
        status=TaskStatus.PENDING,
        assigned_to=AgentType.ORCHESTRATOR,
    )
    return ConductorTask(**{**defaults, **kwargs})


def test_valid_transition():
    task = make_task(status=TaskStatus.PENDING)
    task.transition(TaskStatus.IN_PROGRESS_DEV)
    assert task.status == TaskStatus.IN_PROGRESS_DEV


def test_transition_records_history():
    task = make_task(status=TaskStatus.PENDING)
    task.transition(TaskStatus.IN_PROGRESS_DEV)
    assert len(task.history) == 1
    assert task.history[0]["from"] == "pending"
    assert task.history[0]["to"] == "in_progress_dev"


def test_invalid_transition_raises():
    task = make_task(status=TaskStatus.PENDING)
    with pytest.raises(ValueError, match="Cannot transition"):
        task.transition(TaskStatus.DONE)


def test_terminal_state_raises():
    task = make_task(status=TaskStatus.DONE)
    with pytest.raises(ValueError, match="terminal state"):
        task.transition(TaskStatus.PENDING)


def test_multi_step_transition():
    task = make_task(status=TaskStatus.PENDING)
    task.transition(TaskStatus.IN_PROGRESS_DEV)
    task.transition(TaskStatus.IN_PROGRESS_QA)
    task.transition(TaskStatus.READY_FOR_DEPLOY)
    assert task.status == TaskStatus.READY_FOR_DEPLOY
    assert len(task.history) == 3


def test_needs_work_cycle():
    task = make_task(status=TaskStatus.IN_PROGRESS_DEV)
    task.transition(TaskStatus.NEEDS_WORK)
    task.transition(TaskStatus.IN_PROGRESS_DEV)
    assert task.status == TaskStatus.IN_PROGRESS_DEV
