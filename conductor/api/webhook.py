import logging

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Request

from conductor.adapters.linear.signature import verify_linear_signature
from conductor.config import settings
from conductor.core.domain.task import TaskStatus
from conductor.core.orchestrator import Orchestrator
from conductor.core.ports.adapter_port import AdapterPort

logger = logging.getLogger(__name__)

app = FastAPI(title="Conductor", version="0.1.0")

# Registries injected at startup (populated in main.py)
adapter_registry: dict[str, AdapterPort] = {}
orchestrator: Orchestrator | None = None

_TERMINAL_STATUSES = {TaskStatus.DONE}
_MAX_PIPELINE_STEPS = 10


async def _process(adapter: AdapterPort, payload: dict) -> None:  # type: ignore[type-arg]
    """Background task: translate payload → task → drive full pipeline → publish result.

    Loops through agents until the task reaches a terminal status (DONE) or the
    safety limit is hit. Always calls adapter.from_task() so the source channel
    receives an update even on failure.
    """
    assert orchestrator is not None, "Orchestrator not initialised"
    task = await adapter.to_task(payload)
    try:
        steps = 0
        while task.status not in _TERMINAL_STATUSES and steps < _MAX_PIPELINE_STEPS:
            steps += 1
            task = await orchestrator.handle(task)
        if steps >= _MAX_PIPELINE_STEPS:
            logger.error(
                "Pipeline hit max steps (%d) for task %s — possible loop",
                _MAX_PIPELINE_STEPS,
                task.id,
            )
    except Exception:
        logger.exception("Pipeline failed for task %s", task.id)
    finally:
        await adapter.from_task(task)


async def _verify_linear_signature(
    request: Request,
    linear_signature: str | None = Header(default=None, alias="Linear-Signature"),
) -> None:
    """FastAPI dependency: verify the Linear-Signature HMAC header.

    If LINEAR_WEBHOOK_SECRET is not configured, skips verification and logs a
    warning (useful for local dev). In production, always set the secret.
    """
    secret = settings.linear_webhook_secret
    if not secret:
        logger.warning("LINEAR_WEBHOOK_SECRET not set — skipping signature verification")
        return
    if not linear_signature:
        raise HTTPException(status_code=401, detail="Missing Linear-Signature header")
    body = await request.body()
    if not verify_linear_signature(body, linear_signature, secret):
        raise HTTPException(status_code=401, detail="Invalid signature")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# NOTE: /webhook/linear must be registered BEFORE /webhook/{source} so FastAPI
# matches the specific route first.
@app.post("/webhook/linear", dependencies=[Depends(_verify_linear_signature)])
async def receive_linear_webhook(
    request: Request,
    background: BackgroundTasks,
) -> dict[str, str]:
    """Linear-specific webhook endpoint with HMAC signature verification."""
    adapter = adapter_registry.get("linear")
    if not adapter:
        raise HTTPException(status_code=404, detail="No adapter registered for source: linear")
    payload = await request.json()
    background.add_task(_process, adapter, payload)
    return {"status": "accepted"}


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
