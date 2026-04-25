"""Main entry point for audiobook generator."""
import structlog

from src.config.logging_config import configure
from src.config.config import CLIConfig
from src.workflows.workflow_factory import create_workflow
from src.repository.url_mapper import get_book_id_from_url

logger = structlog.get_logger(__name__)


def main() -> None:
    """Main entry point - parse CLI arguments and execute workflow."""
    configure()
    config = CLIConfig.from_cli()
    workflow = create_workflow(config.workflow)

    if config.url is None:
        raise ValueError(f"--url is required for --workflow {config.workflow}")

    if config.workflow in ("parse", "ai"):
        workflow.run(config.url, **config.run_kwargs())
    else:
        book_id = get_book_id_from_url(config.url)
        workflow.run(book_id)

    logger.info("workflow_complete", workflow=config.workflow)


if __name__ == "__main__":
    main()
