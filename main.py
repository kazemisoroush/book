"""Main entry point for audiobook generator."""
import argparse
import json
import sys
from src.workflows.project_gutenberg_workflow import (
    ProjectGutenbergWorkflow
)


def main():
    """Main entry point - parse CLI arguments and execute workflow."""
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

        # Output to file or stdout
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(json_output)
        else:
            print(json_output)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
