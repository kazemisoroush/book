"""Main entry point for audiobook generator."""
from src.config.cli_config import CLIConfig
from src.config.logging_config import configure
from src.workflows.run_workflow import run_workflow


def main() -> None:
    """Main entry point - parse CLI arguments and execute workflow."""
    configure()
    config = CLIConfig.from_cli()
    run_workflow(
        config.workflow,
        url=config.url,
        start_chapter=config.start_chapter,
        end_chapter=config.end_chapter,
        refresh=config.refresh,
        provider=config.provider,
    )


if __name__ == "__main__":
    main()
