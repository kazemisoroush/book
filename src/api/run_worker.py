"""AWS Lambda entrypoint that runs one workflow invocation and records its terminal status."""
from datetime import datetime, timezone
from typing import Any, Optional

import structlog

from src.api.run_store import RunStore
from src.api.runner import FAILED, SUCCEEDED, RunStatus
from src.config.logging_config import configure
from src.config.provider_secrets import load_provider_secret
from src.storage.storage_factory import create_storage
from src.workflows.run_workflow import run_workflow

logger = structlog.get_logger(__name__)

_OPTIONAL_KEYS = ("start_chapter", "end_chapter", "refresh", "provider")


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    """Run the workflow described by *event*, record its terminal status, and report it."""
    del context
    configure()
    load_provider_secret()
    store = RunStore(create_storage())
    run_id = event.get("run_id")
    workflow = event["workflow"]
    optional = {key: event[key] for key in _OPTIONAL_KEYS if key in event}
    try:
        run_workflow(workflow, url=event["url"], **optional)
    except Exception:
        logger.exception("worker_run_failed", run_id=run_id, workflow=workflow)
        _finalize(store, run_id, workflow, FAILED)
        return {"workflow": workflow, "state": FAILED}
    _finalize(store, run_id, workflow, SUCCEEDED)
    return {"workflow": workflow, "state": SUCCEEDED}


def _finalize(store: RunStore, run_id: Optional[str], workflow: str, state: str) -> None:
    """Write the run's terminal state to the shared store, preserving its started_at."""
    if run_id is None:
        return
    status = store.read_status(run_id) or RunStatus(
        run_id=run_id, workflow=workflow, params={}, state=state,
    )
    status.state = state
    status.ended_at = datetime.now(timezone.utc).isoformat()
    store.write_status(status)
