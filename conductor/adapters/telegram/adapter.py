"""Telegram adapter — inbound message → ConductorTask.

Inbound:  Telegram update payload → ConductorTask
Outbound: ConductorTask result → Telegram reply via Bot API

Project resolution uses a lightweight LLM call (ProjectExtractor) to identify
which project the user message refers to, based on known project names and aliases.
"""

import json
import logging
import uuid
from dataclasses import dataclass

import httpx

from conductor.core.domain.task import AgentType, ConductorProject, ConductorTask, TaskStatus
from conductor.core.ports.adapter_port import AdapterPort
from conductor.core.ports.llm_port import LLMPort
from conductor.core.ports.project_registry_port import ProjectRegistryPort

log = logging.getLogger(__name__)

_MIN_CONFIDENCE = 0.6
_TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"

_EXTRACTOR_SYSTEM = (
    "You are a project classifier. Given a list of known projects and a user message, "
    "return JSON identifying which project the message refers to, or null if none.\n\n"
    "Respond ONLY with valid JSON in this exact format:\n"
    '{"project_id": "<id or null>", "confidence": <0.0-1.0>}'
)


@dataclass
class ProjectExtractionResult:
    project_id: str | None
    confidence: float


class ProjectExtractor:
    """Uses an LLM to map a free-text message to a registered project."""

    def __init__(self, llm: LLMPort, registry: ProjectRegistryPort | None) -> None:
        self._llm = llm
        self._registry = registry

    async def extract(self, message: str) -> ConductorProject | None:
        if self._registry is None:
            return None
        projects = self._registry.get_all()
        if not projects:
            return None
        projects_context = "\n".join(
            f"- id={p.id}, name={p.name}, aliases={p.aliases}" for p in projects
        )
        user_prompt = f"Known projects:\n{projects_context}\n\nUser message:\n{message}"
        raw = await self._llm.run(
            system_prompt=_EXTRACTOR_SYSTEM,
            user_prompt=user_prompt,
            tools=[],
        )
        try:
            data = json.loads(raw)
            result = ProjectExtractionResult(
                project_id=data.get("project_id"),
                confidence=float(data.get("confidence", 0.0)),
            )
        except (json.JSONDecodeError, KeyError, ValueError):
            return None
        if result.project_id is None or result.confidence < _MIN_CONFIDENCE:
            return None
        return self._registry.get_by_id(result.project_id)


class TelegramAdapter(AdapterPort):
    """AdapterPort implementation for Telegram bot messages."""

    def __init__(self, bot_token: str, extractor: ProjectExtractor) -> None:
        self._token = bot_token
        self._extractor = extractor

    async def to_task(self, payload: dict) -> ConductorTask:  # type: ignore[type-arg]
        """Translate a Telegram update payload into a ConductorTask.

        Uses ProjectExtractor to resolve which project the message belongs to.
        If no project is identified, task.project is None and the orchestrator
        will route it to the Researcher agent only.
        """
        msg = payload.get("message") or {}
        text = msg.get("text") or ""
        chat_id = str((msg.get("chat") or {}).get("id", ""))
        project = await self._extractor.extract(text)
        return ConductorTask(
            id=str(uuid.uuid4()),
            external_id=str(msg.get("message_id", "")),
            source="telegram",
            title=text[:80] if text else "(no message)",
            spec=text,
            status=TaskStatus.PENDING,
            assigned_to=AgentType.ORCHESTRATOR,
            project=project,
            metadata={"telegram_chat_id": chat_id},
        )

    async def from_task(self, task: ConductorTask) -> None:
        """Post the final task result back to the originating Telegram chat."""
        chat_id = task.metadata.get("telegram_chat_id")
        if not chat_id:
            log.warning("No telegram_chat_id in task %s metadata — skipping reply", task.id)
            return

        last_agent_entry = next(
            (e for e in reversed(task.history) if "result" in e),
            None,
        )
        reply_text = (last_agent_entry or {}).get("result") or f"Task {task.status.value}."

        url = _TELEGRAM_API.format(token=self._token)
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    url,
                    json={"chat_id": chat_id, "text": reply_text[:4096]},
                    timeout=10,
                )
                resp.raise_for_status()
        except Exception:
            log.exception("Failed to send Telegram reply for task %s", task.id)
