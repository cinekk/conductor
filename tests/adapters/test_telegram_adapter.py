"""Tests for TelegramAdapter and ProjectExtractor."""

import json
import textwrap
import uuid

import pytest

from conductor.adapters.project.yaml_registry import YamlProjectRegistry
from conductor.adapters.telegram.adapter import ProjectExtractor, TelegramAdapter
from conductor.core.domain.task import TaskStatus
from conductor.core.ports.llm_port import LLMPort


class MockLLMAdapter(LLMPort):
    """Local stub — avoids importing claude_agent_sdk."""

    def __init__(self, response: str = "mock response") -> None:
        self._response = response

    async def run(
        self,
        system_prompt: str,
        user_prompt: str,
        tools: list[str] | None = None,
    ) -> str:
        return self._response


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def registry(tmp_path):
    content = textwrap.dedent("""\
        projects:
          - id: flowfocus
            name: FlowFocus
            repo_url: git@github.com:org/flowfocus.git
            aliases:
              - flow
              - ff
          - id: conductor
            name: Conductor
            repo_url: git@github.com:cinekk/conductor.git
            aliases:
              - conductor
    """)
    p = tmp_path / "projects.yaml"
    p.write_text(content)
    return YamlProjectRegistry(str(p))


def make_extractor(llm_response: str, registry) -> ProjectExtractor:
    llm = MockLLMAdapter(response=llm_response)
    return ProjectExtractor(llm=llm, registry=registry)


TELEGRAM_PAYLOAD = {
    "update_id": 100,
    "message": {
        "message_id": 42,
        "text": "Can you check the FlowFocus login bug?",
    },
}


# ---------------------------------------------------------------------------
# ProjectExtractor tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extractor_resolves_known_project(registry):
    response = json.dumps({"project_id": "flowfocus", "confidence": 0.95})
    extractor = make_extractor(response, registry)
    project = await extractor.extract("Fix FlowFocus login bug")
    assert project is not None
    assert project.id == "flowfocus"


@pytest.mark.asyncio
async def test_extractor_returns_none_when_llm_says_null(registry):
    response = json.dumps({"project_id": None, "confidence": 0.1})
    extractor = make_extractor(response, registry)
    project = await extractor.extract("What is the weather today?")
    assert project is None


@pytest.mark.asyncio
async def test_extractor_returns_none_for_unknown_project_id(registry):
    response = json.dumps({"project_id": "nonexistent", "confidence": 0.8})
    extractor = make_extractor(response, registry)
    project = await extractor.extract("Do something with nonexistent")
    assert project is None


@pytest.mark.asyncio
async def test_extractor_returns_none_on_invalid_json(registry):
    extractor = make_extractor("not json at all", registry)
    project = await extractor.extract("some message")
    assert project is None


@pytest.mark.asyncio
async def test_extractor_returns_none_below_confidence_threshold(registry):
    response = json.dumps({"project_id": "flowfocus", "confidence": 0.4})
    extractor = make_extractor(response, registry)
    project = await extractor.extract("Maybe FlowFocus?")
    assert project is None


@pytest.mark.asyncio
async def test_extractor_returns_none_when_registry_empty(tmp_path):
    p = tmp_path / "empty.yaml"
    p.write_text("projects: []\n")
    empty_registry = YamlProjectRegistry(str(p))
    extractor = make_extractor(
        json.dumps({"project_id": "anything", "confidence": 1.0}), empty_registry
    )
    project = await extractor.extract("any message")
    assert project is None


# ---------------------------------------------------------------------------
# TelegramAdapter tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_to_task_with_resolved_project(registry):
    response = json.dumps({"project_id": "conductor", "confidence": 0.9})
    extractor = make_extractor(response, registry)
    adapter = TelegramAdapter(bot_token="test-token", extractor=extractor)
    task = await adapter.to_task(TELEGRAM_PAYLOAD)

    assert task.source == "telegram"
    assert task.external_id == "42"
    assert task.status == TaskStatus.PENDING
    assert task.project is not None
    assert task.project.id == "conductor"
    assert task.project.repo_url == "git@github.com:cinekk/conductor.git"


@pytest.mark.asyncio
async def test_to_task_project_none_when_not_identified(registry):
    response = json.dumps({"project_id": None, "confidence": 0.0})
    extractor = make_extractor(response, registry)
    adapter = TelegramAdapter(bot_token="test-token", extractor=extractor)
    task = await adapter.to_task(TELEGRAM_PAYLOAD)

    assert task.project is None


@pytest.mark.asyncio
async def test_to_task_title_truncated_to_80_chars(registry):
    response = json.dumps({"project_id": None, "confidence": 0.0})
    extractor = make_extractor(response, registry)
    adapter = TelegramAdapter(bot_token="test-token", extractor=extractor)
    long_message = "x" * 200
    payload = {"message": {"message_id": 1, "text": long_message}}
    task = await adapter.to_task(payload)
    assert len(task.title) == 80


@pytest.mark.asyncio
async def test_to_task_empty_message(registry):
    response = json.dumps({"project_id": None, "confidence": 0.0})
    extractor = make_extractor(response, registry)
    adapter = TelegramAdapter(bot_token="test-token", extractor=extractor)
    task = await adapter.to_task({"message": {"message_id": 1, "text": ""}})
    assert task.title == "(no message)"
    assert task.spec == ""


@pytest.mark.asyncio
async def test_from_task_skips_reply_when_no_chat_id(registry):
    """from_task should not raise when telegram_chat_id is absent in metadata."""
    import uuid as _uuid
    from conductor.core.domain.task import AgentType, ConductorTask

    response = json.dumps({"project_id": None, "confidence": 0.0})
    extractor = make_extractor(response, registry)
    adapter = TelegramAdapter(bot_token="test-token", extractor=extractor)
    task = ConductorTask(
        id=str(_uuid.uuid4()),
        external_id="1",
        source="telegram",
        title="T",
        spec="",
        status=TaskStatus.PENDING,
        assigned_to=AgentType.ORCHESTRATOR,
        # no telegram_chat_id in metadata → from_task returns early without HTTP call
    )
    await adapter.from_task(task)  # should not raise


@pytest.mark.asyncio
async def test_to_task_stores_chat_id_in_metadata(registry):
    """to_task should capture the chat id so from_task can reply."""
    response = json.dumps({"project_id": None, "confidence": 0.0})
    extractor = make_extractor(response, registry)
    adapter = TelegramAdapter(bot_token="test-token", extractor=extractor)
    payload = {
        "message": {
            "message_id": 7,
            "text": "hello",
            "chat": {"id": 123456},
        }
    }
    task = await adapter.to_task(payload)
    assert task.metadata.get("telegram_chat_id") == "123456"
