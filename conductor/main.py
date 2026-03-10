"""Application entry point.

Wires together the adapters, orchestrator, and FastAPI app.
"""

import logging

import uvicorn

import conductor.api.webhook as webhook_module
from conductor.adapters.agents.agent_impls import (
    DeployerAgent,
    DeveloperAgent,
    OrchestratorAgent,
    QAAgent,
    ResearcherAgent,
)
from conductor.adapters.agents.claude_agent import ClaudeAgentAdapter
from conductor.adapters.linear.adapter import LinearAdapter
from conductor.adapters.linear.client import LinearClient
from conductor.api.webhook import app  # noqa: F401  (re-exported for uvicorn)
from conductor.config import settings
from conductor.core.domain.task import AgentType
from conductor.core.orchestrator import Orchestrator
from conductor.observability import setup_tracing
from conductor.prompts import PromptRegistry

logging.basicConfig(level=settings.log_level.upper())


def build_app() -> None:
    """Initialise registries. Called once at startup."""
    setup_tracing()

    prompts = PromptRegistry()

    agent_registry: dict[AgentType, object] = {
        AgentType.ORCHESTRATOR: OrchestratorAgent(
            llm=ClaudeAgentAdapter(allowed_tools=["Read"]),
            prompts=prompts,
        ),
        AgentType.DEVELOPER: DeveloperAgent(
            llm=ClaudeAgentAdapter(allowed_tools=["Read", "Write", "Edit", "Bash"]),
            prompts=prompts,
        ),
        AgentType.QA: QAAgent(
            llm=ClaudeAgentAdapter(allowed_tools=["Read", "Bash"]),
            prompts=prompts,
        ),
        AgentType.DEPLOYER: DeployerAgent(
            llm=ClaudeAgentAdapter(allowed_tools=["Read", "Bash"]),
            prompts=prompts,
        ),
        AgentType.RESEARCHER: ResearcherAgent(
            llm=ClaudeAgentAdapter(allowed_tools=["Read"]),
            prompts=prompts,
        ),
    }

    orch = Orchestrator(agent_registry=agent_registry)  # type: ignore[arg-type]
    webhook_module.orchestrator = orch

    # Linear adapter — only register if credentials are configured
    if settings.linear_api_key and settings.linear_team_id:
        linear_client = LinearClient(api_key=settings.linear_api_key)
        linear_adapter = LinearAdapter(client=linear_client, team_id=settings.linear_team_id)
        webhook_module.adapter_registry["linear"] = linear_adapter
        logging.getLogger(__name__).info("LinearAdapter registered")
    else:
        logging.getLogger(__name__).warning(
            "LINEAR_API_KEY or LINEAR_TEAM_ID not set — LinearAdapter not registered"
        )


build_app()

if __name__ == "__main__":
    uvicorn.run("conductor.main:app", host="0.0.0.0", port=8000, reload=True)
