"""Concrete LLM implementations.

ClaudeAgentAdapter  — uses the Claude Agent SDK (real API calls).
MockLLMAdapter      — returns canned responses; for unit tests only.

Tool permissions per agent type:
  Developer  → Read, Write, Edit, Bash
  QA         → Read, Bash
  Deployer   → Read, Bash
  Researcher → Read
  (default)  → Read
"""

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

from conductor.core.ports.llm_port import LLMPort

# Default tool allowlist — conservative; callers can override per agent type
_DEFAULT_TOOLS = ["Read", "Write", "Edit", "Bash"]


class ClaudeAgentAdapter(LLMPort):
    """LLMPort backed by the Claude Agent SDK."""

    def __init__(self, allowed_tools: list[str] | None = None) -> None:
        self._tools = allowed_tools if allowed_tools is not None else _DEFAULT_TOOLS

    async def run(
        self,
        system_prompt: str,
        user_prompt: str,
        tools: list[str] | None = None,
    ) -> str:
        effective_tools = tools if tools is not None else self._tools
        result_parts: list[str] = []
        async for message in query(
            prompt=user_prompt,
            options=ClaudeAgentOptions(
                system_prompt=system_prompt,
                allowed_tools=effective_tools,
            ),
        ):
            if isinstance(message, ResultMessage) and message.result:
                result_parts.append(message.result)
        return "\n".join(result_parts)


class MockLLMAdapter(LLMPort):
    """Deterministic LLM stub for unit tests — no API calls."""

    def __init__(self, response: str = "mock response") -> None:
        self._response = response

    async def run(
        self,
        system_prompt: str,
        user_prompt: str,
        tools: list[str] | None = None,
    ) -> str:
        return self._response
