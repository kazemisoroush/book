"""Main entry point for audiobook generator."""
import argparse
import json
import sys

import structlog

from src.logging_config import configure
from src.workflows.project_gutenberg_workflow import (
    ProjectGutenbergWorkflow
)

logger = structlog.get_logger(__name__)


def main() -> None:
    """Main entry point - parse CLI arguments and execute workflow."""
    # Configure structured logging before anything else
    configure()

    parser = argparse.ArgumentParser(
        description='Parse Project Gutenberg books into JSON'
    )
    parser.add_argument(
        'url',
        help='Project Gutenberg book URL (e.g., https://www.gutenberg.org/files/123/123-h.zip)'  # noqa: E501
    )
    parser.add_argument(
        '-o', '--output',
        help='Output file path (if not specified, prints to stdout)',
        default=None
    )

    args = parser.parse_args()

    # Create workflow with factory (includes AI section parser by default)
    workflow = ProjectGutenbergWorkflow.create()

    try:
        book = workflow.run(args.url)

        # Convert to JSON
        json_output = json.dumps(book.to_dict(), indent=2, ensure_ascii=False)

        # Output to file or stdout — this is data output, not a log message
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(json_output)
        else:
            print(json_output)

    except Exception as e:
        logger.error("workflow_error", error=str(e), exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
