"""The event contract between the API runner and the worker Lambda, defined once."""
from typing import Any

from src.api.runner import RunParams

_PARAM_KEYS = ("start_chapter", "end_chapter", "refresh", "provider")


def to_event(run_id: str, workflow: str, params: RunParams) -> dict[str, Any]:
    """Build the worker invocation payload for a run."""
    event: dict[str, Any] = {"run_id": run_id, "workflow": workflow, "url": params.url}
    for key in _PARAM_KEYS:
        event[key] = getattr(params, key)
    return event


def workflow_args(event: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    """Split an event into the workflow name, url, and optional kwargs for run_workflow."""
    optional = {key: event[key] for key in _PARAM_KEYS if key in event}
    return event["workflow"], event["url"], optional
