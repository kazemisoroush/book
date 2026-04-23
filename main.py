"""Main entry point for audiobook generator."""
import structlog

from src.config.logging_config import configure
from src.config.config import CLIConfig
from src.workflows.workflow_factory import create_workflow

logger = structlog.get_logger(__name__)


def main() -> None:
    """Main entry point - parse CLI arguments and execute workflow."""
    configure()
    config = CLIConfig.from_cli()
    workflow = create_workflow(config.workflow)

    if config.url is None:
        raise ValueError(f"--url is required for --workflow {config.workflow}")

    workflow.run(config.url, **config.run_kwargs())
    logger.info("workflow_complete", workflow=config.workflow)


if __name__ == "__main__":
    main()
