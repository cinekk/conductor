"""Prompt versioning for Conductor agents.

Prompts live in conductor/prompt_templates/ as plain-text files.
Each file name encodes name and version: <name>@<version>.txt
The special version "latest" resolves to the highest version number.

Usage::

    registry = PromptRegistry()
    system_prompt = registry.get("developer-agent")           # latest
    system_prompt = registry.get("developer-agent", version=2) # pinned

Template variables are filled with str.format_map():

    system_prompt = registry.get("developer-agent", spec=task.spec)

This is intentionally simple — swap for Langfuse Prompt Management
when the Python SDK supports Python 3.14.
"""

from __future__ import annotations

import re
from pathlib import Path

_TEMPLATE_DIR = Path(__file__).parent / "prompt_templates"
_FILE_RE = re.compile(r"^(?P<name>.+)@(?P<version>\d+)\.txt$")


class PromptNotFoundError(Exception):
    """Raised when no template file matches the requested name/version."""


class PromptRegistry:
    """Loads and caches prompt templates from the filesystem."""

    def __init__(self, template_dir: Path = _TEMPLATE_DIR) -> None:
        self._dir = template_dir
        # {name: {version: text}}
        self._cache: dict[str, dict[int, str]] = {}
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, name: str, version: int | str = "latest", **kwargs: object) -> str:
        """Return the prompt template, optionally filled with *kwargs*.

        Args:
            name:    Template name (e.g. "developer-agent").
            version: Integer version or "latest" (default).
            **kwargs: Variables substituted into the template.

        Raises:
            PromptNotFoundError: When no matching template file exists.
        """
        versions = self._cache.get(name)
        if not versions:
            raise PromptNotFoundError(f"No prompt templates found for {name!r}")

        if version == "latest":
            resolved = max(versions)
        else:
            resolved = int(version)
            if resolved not in versions:
                raise PromptNotFoundError(
                    f"Prompt {name!r} version {resolved} not found. "
                    f"Available: {sorted(versions)}"
                )

        text = versions[resolved]
        return text.format_map(kwargs) if kwargs else text

    def available(self) -> dict[str, list[int]]:
        """Return {name: [versions]} for every loaded template."""
        return {name: sorted(v) for name, v in self._cache.items()}

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if not self._dir.is_dir():
            return
        for path in self._dir.glob("*.txt"):
            m = _FILE_RE.match(path.name)
            if not m:
                continue
            name = m.group("name")
            version = int(m.group("version"))
            self._cache.setdefault(name, {})[version] = path.read_text(encoding="utf-8")
