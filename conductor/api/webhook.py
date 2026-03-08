from fastapi import BackgroundTasks, FastAPI, HTTPException, Request

from conductor.core.orchestrator import Orchestrator
from conductor.core.ports.adapter_port import AdapterPort

app = FastAPI(title="Conductor", version="0.1.0")

# Registries injected at startup (populated in main.py)
adapter_registry: dict[str, AdapterPort] = {}
orchestrator: Orchestrator | None = None


async def _process(adapter: AdapterPort, payload: dict) -> None:  # type: ignore[type-arg]
    """Background task: translate payload → task → orchestrate → publish result."""
    assert orchestrator is not None, "Orchestrator not initialised"
    task = await adapter.to_task(payload)
    updated = await orchestrator.handle(task)
    await adapter.from_task(updated)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/webhook/{source}")
async def receive_webhook(
    source: str,
    request: Request,
    background: BackgroundTasks,
) -> dict[str, str]:
    """Accept a webhook from any registered source and process it asynchronously.

    Returns 200 immediately so the caller (e.g. Linear) doesn't time out while
    the agent does its work in the background.
    """
    adapter = adapter_registry.get(source)
    if not adapter:
        raise HTTPException(status_code=404, detail=f"No adapter registered for source: {source}")
    payload = await request.json()
    background.add_task(_process, adapter, payload)
    return {"status": "accepted"}
