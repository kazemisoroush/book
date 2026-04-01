"""Dispatch shim — run a book-processing workflow from the command line.

Usage:
    python scripts/run_workflow.py --url URL [--chapters 1] [--workflow ai]

Examples:
    python scripts/run_workflow.py --url https://www.gutenberg.org/cache/epub/1342/pg1342-h.zip
    python scripts/run_workflow.py --url https://www.gutenberg.org/cache/epub/1342/pg1342-h.zip --chapters 0
    python scripts/run_workflow.py --url https://www.gutenberg.org/cache/epub/1342/pg1342-h.zip --workflow tts
    python scripts/run_workflow.py --url https://www.gutenberg.org/cache/epub/1342/pg1342-h.zip --reparse
"""
import argparse
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
    parser.add_argument("--chapters", type=int, default=1, help="Chapter limit (default: 1; 0 = all)")
    parser.add_argument(
        "--workflow",
        choices=["parse", "ai", "tts"],
        default="ai",
        help="Workflow to run: parse | ai | tts (default: ai)",
    )
    parser.add_argument(
        "--reparse",
        action="store_true",
        default=False,
        help="Force re-parse even if a cached parsed book exists (default: False)",
    )
    args = parser.parse_args()

    if args.workflow == "parse":
        from src.workflows.project_gutenberg_workflow import ProjectGutenbergWorkflow
        workflow = ProjectGutenbergWorkflow.create()
    elif args.workflow == "ai":
        from src.workflows.ai_project_gutenberg_workflow import AIProjectGutenbergWorkflow
        from src.repository.file_book_repository import FileBookRepository
        repository = FileBookRepository()
        workflow = AIProjectGutenbergWorkflow.create(repository=repository)
    else:  # tts
        from src.workflows.tts_project_gutenberg_workflow import TTSProjectGutenbergWorkflow
        workflow = TTSProjectGutenbergWorkflow.create()

    logger.info("run_workflow_start", workflow=args.workflow, url=args.url, chapters=args.chapters)

    # Only the AI and TTS workflows support reparse; static parse ignores it.
    run_kwargs: dict[str, object] = {"chapter_limit": args.chapters}
    if args.workflow in ("ai", "tts") and args.reparse:
        run_kwargs["reparse"] = True

    workflow.run(args.url, **run_kwargs)  # type: ignore[arg-type]

    logger.info("run_workflow_done")
    print("Done", file=sys.stderr)


if __name__ == "__main__":
    main()
