
import pytest

from conductor.adapters.agents.claude_agent import MockLLMAdapter


@pytest.mark.asyncio
async def test_mock_llm_returns_canned_response():
    adapter = MockLLMAdapter(response="all good")
    result = await adapter.run(system_prompt="sys", user_prompt="do it")
    assert result == "all good"


@pytest.mark.asyncio
async def test_mock_llm_default_response():
    adapter = MockLLMAdapter()
    result = await adapter.run(system_prompt="sys", user_prompt="do it")
    assert result == "mock response"


@pytest.mark.asyncio
async def test_mock_llm_ignores_tools():
    adapter = MockLLMAdapter(response="done")
    result = await adapter.run(system_prompt="s", user_prompt="p", tools=["Read"])
    assert result == "done"
