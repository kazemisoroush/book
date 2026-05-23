"""Main entry point for audiobook generator."""
import structlog

from src.config.cli_config import CLIConfig
from src.config.logging_config import configure
from src.workflows.workflow import WorkflowRequest
from src.workflows.workflow_factory import create_workflow

logger = structlog.get_logger(__name__)


def main() -> None:
    """Main entry point - parse CLI arguments and execute workflow."""
    configure()
    config = CLIConfig.from_cli()
    workflow = create_workflow(config.workflow, provider=config.provider)

    workflow.run(WorkflowRequest(
        url=config.url,
        start_chapter=config.start_chapter,
        end_chapter=config.end_chapter,
        refresh=config.refresh,
    ))

    logger.info("workflow_complete", workflow=config.workflow)


if __name__ == "__main__":
    main()
