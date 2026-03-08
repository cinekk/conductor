"""Application entry point.

Wires together the adapters, orchestrator, and FastAPI app.
Add concrete adapters here as they are implemented in later milestones.
"""

import uvicorn

import conductor.api.webhook as webhook_module
from conductor.api.webhook import adapter_registry, app, orchestrator  # noqa: F401
from conductor.core.domain.task import AgentType
from conductor.core.orchestrator import Orchestrator


def build_app() -> None:
    """Initialise registries. Called once at startup."""
    # Agent registry — populated as real agents are implemented
    agent_registry: dict[AgentType, object] = {}

    orch = Orchestrator(agent_registry=agent_registry)  # type: ignore[arg-type]
    webhook_module.orchestrator = orch

    # Adapter registry — populated in M2/M4 as adapters are implemented
    # e.g. webhook_module.adapter_registry["linear"] = LinearAdapter(...)


build_app()

if __name__ == "__main__":
    uvicorn.run("conductor.main:app", host="0.0.0.0", port=8000, reload=True)
