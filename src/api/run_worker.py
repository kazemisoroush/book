"""AWS Lambda entrypoint that runs one workflow invocation for a chapter range."""
from typing import Any

from src.config.logging_config import configure
from src.workflows.run_workflow import run_workflow


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    """Run the workflow described by *event* and report the outcome."""
    del context
    configure()
    run_workflow(
        event["workflow"],
        url=event["url"],
        start_chapter=event.get("start_chapter", 1),
        end_chapter=event.get("end_chapter"),
        refresh=event.get("refresh", False),
        provider=event.get("provider"),
    )
    return {"workflow": event["workflow"], "state": "succeeded"}
