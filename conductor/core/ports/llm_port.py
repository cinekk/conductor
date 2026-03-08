from abc import ABC, abstractmethod


class LLMPort(ABC):
    """Contract for LLM backends.

    Swap this implementation to switch from Claude to any other model without
    touching the core or the adapters.
    """

    @abstractmethod
    async def run(
        self,
        system_prompt: str,
        user_prompt: str,
        tools: list[str] | None = None,
    ) -> str:
        """Run a prompt against the LLM and return the text result."""
        ...
