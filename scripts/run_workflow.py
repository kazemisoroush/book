"""Dispatch shim — run a book-processing workflow from the command line.

Usage:
    python scripts/run_workflow.py --url URL [--output output.json] [--chapters 3] [--workflow ai]

Examples:
    python scripts/run_workflow.py --url https://www.gutenberg.org/cache/epub/1342/pg1342-h.zip
    python scripts/run_workflow.py --url https://www.gutenberg.org/cache/epub/1342/pg1342-h.zip --chapters 0
    python scripts/run_workflow.py --url https://www.gutenberg.org/cache/epub/1342/pg1342-h.zip --workflow tts
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)

from src.config.logging_config import configure as configure_logging  # noqa: E402

configure_logging()

import structlog  # noqa: E402

logger = structlog.get_logger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a book-processing workflow on a Project Gutenberg URL.",
    )
    parser.add_argument("--url", required=True, help="Project Gutenberg zip URL")
    parser.add_argument("--output", default="output.json", help="Output JSON path (default: output.json)")
    parser.add_argument("--chapters", type=int, default=3, help="Chapter limit (default: 3; 0 = all)")
    parser.add_argument(
        "--workflow",
        choices=["parse", "ai", "tts"],
        default="ai",
        help="Workflow to run: parse | ai | tts (default: ai)",
    )
    args = parser.parse_args()

    if args.workflow == "parse":
        from src.workflows.project_gutenberg_workflow import ProjectGutenbergWorkflow
        workflow = ProjectGutenbergWorkflow.create()
    elif args.workflow == "ai":
        from src.workflows.ai_project_gutenberg_workflow import AIProjectGutenbergWorkflow
        workflow = AIProjectGutenbergWorkflow.create()
    else:  # tts
        from src.workflows.tts_project_gutenberg_workflow import TTSProjectGutenbergWorkflow
        output_dir = Path(args.output).parent / "audio"
        workflow = TTSProjectGutenbergWorkflow.create(output_dir=output_dir)

    logger.info("run_workflow_start", workflow=args.workflow, url=args.url, chapters=args.chapters)

    book = workflow.run(args.url, chapter_limit=args.chapters)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(book.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    logger.info("run_workflow_done", output=str(output_path))
    print(f"Done -> {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
