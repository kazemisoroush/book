"""Dispatch shim — run a book-processing workflow from the command line.

Usage:
    python scripts/run_workflow.py --url URL [--start-chapter N] [--end-chapter M] [--workflow ai]

Examples:
    # Parse all chapters (auto-resumes from cache if it exists)
    python scripts/run_workflow.py --url https://www.gutenberg.org/cache/epub/1342/pg1342-h.zip

    # Parse all chapters (force fresh parse, ignoring cache)
    python scripts/run_workflow.py --url https://www.gutenberg.org/cache/epub/1342/pg1342-h.zip --reparse

    # Parse only chapters 5-15
    python scripts/run_workflow.py --url https://www.gutenberg.org/cache/epub/1342/pg1342-h.zip --start-chapter 5 --end-chapter 15

    # Run TTS workflow (default: 3 chapters)
    python scripts/run_workflow.py --url https://www.gutenberg.org/cache/epub/1342/pg1342-h.zip --workflow tts

    # Backward compat: --chapters still works (maps to chapter_limit for AI/TTS workflows)
    python scripts/run_workflow.py --url https://www.gutenberg.org/cache/epub/1342/pg1342-h.zip --chapters 5
"""
import argparse
import sys
from pathlib import Path
from typing import Union

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
    parser.add_argument(
        "--chapters",
        type=int,
        default=None,
        help="Chapter limit (deprecated; use --end-chapter instead). Default: None (all chapters)",
    )
    parser.add_argument(
        "--start-chapter",
        type=int,
        default=1,
        help="1-based chapter index to begin parsing (default: 1; auto-resumes from cache if exists)",
    )
    parser.add_argument(
        "--end-chapter",
        type=int,
        default=None,
        help="1-based chapter index to end parsing (inclusive). Default: None (all chapters)",
    )
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
    parser.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help="Keep individual segment MP3 files alongside chapter.mp3 (default: False)",
    )
    # Feature flags
    parser.add_argument(
        "--enable-ambient",
        action="store_true",
        help="Enable ambient background sound (default: enabled)",
    )
    parser.add_argument(
        "--disable-ambient",
        action="store_true",
        help="Disable ambient background sound",
    )
    parser.add_argument(
        "--enable-cinematic-sfx",
        action="store_true",
        help="Enable cinematic sound effects (default: enabled)",
    )
    parser.add_argument(
        "--disable-cinematic-sfx",
        action="store_true",
        help="Disable cinematic sound effects",
    )
    parser.add_argument(
        "--enable-emotion",
        action="store_true",
        help="Enable emotion tags (default: enabled)",
    )
    parser.add_argument(
        "--disable-emotion",
        action="store_true",
        help="Disable emotion tags",
    )
    parser.add_argument(
        "--enable-voice-design",
        action="store_true",
        help="Enable voice design (default: enabled)",
    )
    parser.add_argument(
        "--disable-voice-design",
        action="store_true",
        help="Disable voice design",
    )
    parser.add_argument(
        "--enable-scene-context",
        action="store_true",
        help="Enable scene context (default: enabled)",
    )
    parser.add_argument(
        "--disable-scene-context",
        action="store_true",
        help="Disable scene context",
    )
    args = parser.parse_args()

    from src.workflows.project_gutenberg_workflow import ProjectGutenbergWorkflow
    from src.workflows.ai_project_gutenberg_workflow import AIProjectGutenbergWorkflow
    from src.workflows.tts_project_gutenberg_workflow import TTSProjectGutenbergWorkflow

    workflow: Union[ProjectGutenbergWorkflow, AIProjectGutenbergWorkflow, TTSProjectGutenbergWorkflow]

    if args.workflow == "parse":
        workflow = ProjectGutenbergWorkflow.create()
    elif args.workflow == "ai":
        from src.repository.file_book_repository import FileBookRepository
        repository = FileBookRepository()
        workflow = AIProjectGutenbergWorkflow.create(repository=repository)
    else:  # tts
        workflow = TTSProjectGutenbergWorkflow.create()

    logger.info(
        "run_workflow_start",
        workflow=args.workflow,
        url=args.url,
        chapters=args.chapters,
        start_chapter=args.start_chapter,
        end_chapter=args.end_chapter,
    )

    # Only the AI and TTS workflows support the new chapter parameters; static parse ignores them.
    # Backward compatibility: if --chapters is provided, use it as chapter_limit
    run_kwargs: dict[str, object] = {}

    if args.workflow in ("ai", "tts"):
        # Use new start_chapter and end_chapter parameters
        run_kwargs["start_chapter"] = args.start_chapter
        if args.end_chapter is not None:
            run_kwargs["end_chapter"] = args.end_chapter
        # Backward compat: if --chapters is provided, use it as chapter_limit
        if args.chapters is not None:
            run_kwargs["chapter_limit"] = args.chapters
        if args.reparse:
            run_kwargs["reparse"] = True
    else:
        # Static parse workflow still uses chapter_limit
        run_kwargs["chapter_limit"] = args.chapters if args.chapters is not None else 0
    if args.workflow == "tts" and args.debug:
        run_kwargs["debug"] = True

    # Feature flags (TTS workflow only)
    if args.workflow == "tts":
        # Helper to resolve --enable and --disable flags (--disable takes precedence)
        def resolve_flag(enable_flag: bool, disable_flag: bool) -> bool:
            if disable_flag:
                return False
            if enable_flag:
                return True
            return True  # Default enabled

        if args.disable_ambient or args.enable_ambient:
            run_kwargs["ambient_enabled"] = resolve_flag(args.enable_ambient, args.disable_ambient)
        if args.disable_cinematic_sfx or args.enable_cinematic_sfx:
            run_kwargs["cinematic_sfx_enabled"] = resolve_flag(
                args.enable_cinematic_sfx, args.disable_cinematic_sfx
            )
        if args.disable_emotion or args.enable_emotion:
            run_kwargs["emotion_enabled"] = resolve_flag(args.enable_emotion, args.disable_emotion)
        if args.disable_voice_design or args.enable_voice_design:
            run_kwargs["voice_design_enabled"] = resolve_flag(
                args.enable_voice_design, args.disable_voice_design
            )
        if args.disable_scene_context or args.enable_scene_context:
            run_kwargs["scene_context_enabled"] = resolve_flag(
                args.enable_scene_context, args.disable_scene_context
            )

    workflow.run(args.url, **run_kwargs)  # type: ignore[arg-type]

    logger.info("run_workflow_done")
    print("Done", file=sys.stderr)


if __name__ == "__main__":
    main()
