"""Run a single workflow invocation, shared by the CLI and the cloud worker."""
from typing import Optional

import structlog

from src.workflows.workflow import WorkflowRequest
from src.workflows.workflow_factory import create_workflow

logger = structlog.get_logger(__name__)


def run_workflow(
    workflow: str,
    url: Optional[str],
    start_chapter: int = 1,
    end_chapter: Optional[int] = None,
    refresh: bool = False,
    provider: Optional[str] = None,
) -> None:
    """Build the named workflow and run it over the given chapter range."""
    if url is None:
        raise ValueError("url is required to run a workflow")
    instance = create_workflow(workflow, provider=provider)
    instance.run(WorkflowRequest(
        url=url,
        start_chapter=start_chapter,
        end_chapter=end_chapter,
        refresh=refresh,
    ))
    logger.info("workflow_complete", workflow=workflow)
