"""AWS Lambda entrypoint that runs one workflow invocation for a chapter range."""
from typing import Any

from src.api.runner import SUCCEEDED
from src.config.logging_config import configure
from src.config.provider_secrets import load_provider_secret
from src.workflows.run_workflow import run_workflow

_OPTIONAL_KEYS = ("start_chapter", "end_chapter", "refresh", "provider")


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    """Run the workflow described by *event* and report the outcome."""
    del context
    configure()
    load_provider_secret()
    optional = {key: event[key] for key in _OPTIONAL_KEYS if key in event}
    run_workflow(event["workflow"], url=event["url"], **optional)
    return {"workflow": event["workflow"], "state": SUCCEEDED}
