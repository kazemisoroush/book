"""End-to-end listening eval for the full audiobook pipeline.

Purpose:
    Human-evaluated listening test for full pipeline. Runs the complete
    TTSProjectGutenbergWorkflow on a short passage and writes an MP3 for
    manual review. Prints a structured checklist of what to listen for.

Cost:
    $2.50 - $5.00 per run (varies by passage length and features enabled).

Runtime:
    ~5-8 minutes per run.

Warning:
    This eval makes real API calls and is NOT free. It will consume:
      - AWS Bedrock credits (AI parsing)
      - ElevenLabs credits (TTS, voice design, SFX, ambient)
      - Suno AI credits (background music, if enabled)
    Do NOT run this in CI. Run manually after major pipeline changes.

Usage:
    # Run with explicit URL and chapter range
    python -m src.evals.run_e2e_listening_eval \\
        --url https://www.gutenberg.org/cache/epub/345/pg345.txt \\
        --start-chapter 1 \\
        --end-chapter 1 \\
        --output-dir evals_output/

    # Run using a named golden passage
    python -m src.evals.run_e2e_listening_eval --passage dracula_arrival
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import structlog

from src.config.logging_config import configure
from src.evals.book.fixtures.golden_e2e_passage import (
    ALL_E2E_PASSAGES,
    GoldenE2EPassage,
)

logger = structlog.get_logger(__name__)


def build_arg_parser() -> argparse.ArgumentParser:
    """Build and return the CLI argument parser.

    Returns:
        Configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        description=(
            "End-to-end listening eval — runs the full audiobook pipeline on "
            "a short passage and outputs an MP3 for human review."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Named passage shortcut
    parser.add_argument(
        "--passage",
        metavar="NAME",
        default=None,
        help=(
            "Load a named golden passage (e.g. 'dracula_arrival'). "
            "When provided, --url, --start-chapter, and --end-chapter are "
            "derived from the passage definition."
        ),
    )

    # Explicit overrides (optional when --passage is used)
    parser.add_argument(
        "--url",
        metavar="URL",
        default=None,
        help="Project Gutenberg plain-text URL.",
    )
    parser.add_argument(
        "--start-chapter",
        type=int,
        metavar="N",
        default=None,
        help="1-based chapter index to begin parsing (inclusive).",
    )
    parser.add_argument(
        "--end-chapter",
        type=int,
        metavar="N",
        default=None,
        help="1-based chapter index to end parsing (inclusive).",
    )
    parser.add_argument(
        "--output-dir",
        metavar="DIR",
        default="evals_output",
        help="Base directory for output files (default: evals_output).",
    )
    parser.add_argument(
        "--music",
        action="store_true",
        default=False,
        help="Enable Suno AI background music (requires SUNO_API_KEY).",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help="Keep individual segment MP3 files alongside the stitched chapter.mp3.",
    )
    parser.add_argument(
        "--reparse",
        action="store_true",
        default=False,
        help="Bypass cached book and re-run the full AI pipeline.",
    )
    return parser


def resolve_passage(name: str) -> GoldenE2EPassage:
    """Look up a named passage from the golden registry.

    Args:
        name: Passage slug (e.g. "dracula_arrival").

    Returns:
        Matching GoldenE2EPassage.

    Raises:
        ValueError: If no passage with the given name is found.
    """
    for passage in ALL_E2E_PASSAGES:
        if passage.name == name:
            return passage
    available = ", ".join(p.name for p in ALL_E2E_PASSAGES)
    raise ValueError(
        f"unknown passage '{name}'. Available passages: {available}"
    )


def validate_env_vars(music_enabled: bool = False) -> None:
    """Check that all required environment variables are set.

    Reads from the environment directly — this is the accepted pattern for
    a pre-flight validation check before expensive API calls begin.

    Args:
        music_enabled: When True, also checks SUNO_API_KEY.

    Raises:
        SystemExit: If any required variable is missing, prints a clear error
                    and exits with code 1.
    """
    import os

    required: list[tuple[str, str]] = [
        ("AWS_ACCESS_KEY_ID", "AWS Bedrock (AI parsing)"),
        ("AWS_SECRET_ACCESS_KEY", "AWS Bedrock (AI parsing)"),
        ("ELEVENLABS_API_KEY", "ElevenLabs (TTS, SFX, ambient, voice design)"),
    ]
    if music_enabled:
        required.append(("SUNO_API_KEY", "Suno AI (background music)"))

    missing = [
        (var, service)
        for var, service in required
        if not os.environ.get(var)
    ]

    if missing:
        print("ERROR: The following required environment variables are not set:", file=sys.stderr)
        for var, service in missing:
            print(f"  {var}  — needed for {service}", file=sys.stderr)
        print("\nSet these variables before running the eval.", file=sys.stderr)
        sys.exit(1)


def build_output_dir(base_dir: str, now: Optional[datetime] = None) -> Path:
    """Build a timestamped output directory path.

    Args:
        base_dir: Base directory string (e.g. "evals_output").
        now: Datetime to use for timestamp. Defaults to current UTC time.
             Inject for deterministic testing.

    Returns:
        Path like ``evals_output/e2e-2026-04-10-143022``.
    """
    if now is None:
        now = datetime.utcnow()
    timestamp = now.strftime("%Y-%m-%d-%H%M%S")
    return Path(base_dir) / f"e2e-{timestamp}"


def format_checklist(output_path: Path, duration_seconds: int) -> str:
    """Format the human-readable listening checklist.

    Args:
        output_path: Path to the generated MP3.
        duration_seconds: Total audio duration in seconds.

    Returns:
        Multi-line string suitable for printing to stdout.
    """
    minutes, secs = divmod(duration_seconds, 60)
    duration_str = f"{minutes}:{secs:02d}"

    border = "\u2550" * 62
    lines = [
        "",
        border,
        "E2E LISTENING EVAL \u2014 Generated audio ready for review",
        border,
        "",
        f"Output: {output_path}",
        f"Duration: {duration_str}",
        "",
        "Listen for the following features:",
        "",
        "[ ] NARRATION \u2014 Baseline narrator voice is clear and consistent",
        "[ ] DIALOGUE \u2014 At least 2 distinct character voices",
        "[ ] EMOTION \u2014 At least one segment with vocal emotion (e.g., whispers, laughs)",
        "[ ] SOUND EFFECTS \u2014 Diegetic SFX in silence gaps (e.g., knock, cough, footsteps)",
        "[ ] AMBIENT \u2014 Scene-appropriate background sound at correct volume",
        "[ ] SCENE TRANSITION \u2014 Ambient cross-fade when scene changes (if passage has scene change)",
        "[ ] BACKGROUND MUSIC \u2014 Music underscores emotional tone (if enabled and mood detected)",
        "[ ] VOICE DESIGN \u2014 At least one bespoke character voice matches description",
        "[ ] INTER-SEGMENT SILENCE \u2014 Natural pauses between segments",
        "[ ] NO AUDIO ARTIFACTS \u2014 No clicks, pops, or glitches in stitched audio",
        "",
        "Cost estimate: $2.50 - $5.00 (varies by passage length and features used)",
        "Runtime: ~5-8 minutes",
        "",
    ]
    return "\n".join(lines)


def _get_audio_duration_seconds(audio_path: Path) -> int:
    """Return duration of an MP3 in whole seconds, or 0 on error.

    Attempts to use the ``mutagen`` library if available, otherwise falls back
    to returning 0 (the checklist will still print but without an accurate
    duration).

    Args:
        audio_path: Path to the MP3 file.

    Returns:
        Duration in seconds, or 0 if the library is unavailable or the file
        cannot be read.
    """
    try:
        import importlib

        mutagen_mp3 = importlib.import_module("mutagen.mp3")
        audio = mutagen_mp3.MP3(str(audio_path))
        return int(audio.info.length)
    except Exception:  # noqa: BLE001
        return 0


def main() -> None:
    """Entry point for the E2E listening eval.

    Parses CLI args, validates environment, runs the full pipeline,
    then prints the listening checklist. Exits 0 on success.
    """
    configure()

    parser = build_arg_parser()
    args = parser.parse_args()

    # Resolve URL + chapter range from --passage or explicit flags
    if args.passage is not None:
        passage = resolve_passage(args.passage)
        url = args.url or passage.gutenberg_url
        start_chapter = args.start_chapter or passage.start_chapter
        end_chapter = args.end_chapter or passage.end_chapter
    else:
        if args.url is None or args.start_chapter is None or args.end_chapter is None:
            parser.error(
                "Either --passage or all of --url, --start-chapter, --end-chapter are required."
            )
        url = args.url
        start_chapter = args.start_chapter
        end_chapter = args.end_chapter

    music_enabled: bool = args.music

    # Pre-flight env var check — fail fast before spending any API budget
    validate_env_vars(music_enabled=music_enabled)

    # Build output directory
    output_dir = build_output_dir(base_dir=args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(
        "e2e_eval_starting",
        url=url,
        start_chapter=start_chapter,
        end_chapter=end_chapter,
        output_dir=str(output_dir),
        music_enabled=music_enabled,
    )

    print("\nRunning E2E listening eval...")
    print(f"URL:     {url}")
    print(f"Chapters: {start_chapter} to {end_chapter}")
    print(f"Output:  {output_dir}/")
    print()

    # Import lazily so the module can be imported without all dependencies
    from src.config.feature_flags import FeatureFlags
    from src.workflows.tts_project_gutenberg_workflow import TTSProjectGutenbergWorkflow

    books_dir = output_dir / "books"
    books_dir.mkdir(parents=True, exist_ok=True)

    feature_flags = FeatureFlags(
        ambient_enabled=True,
        sound_effects_enabled=True,
        emotion_enabled=True,
        voice_design_enabled=True,
        scene_context_enabled=True,
        chapter_announcer_enabled=True,
    )

    workflow = TTSProjectGutenbergWorkflow.create(books_dir=books_dir)

    book = workflow.run(
        url=url,
        start_chapter=start_chapter,
        end_chapter=end_chapter,
        reparse=args.reparse,
        debug=args.debug,
        feature_flags=feature_flags,
    )

    # Find the generated chapter audio file
    from src.repository.book_id import generate_book_id

    book_id = generate_book_id(book.metadata)
    audio_dir = books_dir / book_id / "audio"

    # Look for the chapter MP3 from the first chapter in range
    chapter_mp3: Optional[Path] = None
    for chapter_num in range(start_chapter, end_chapter + 1):
        candidate = audio_dir / f"chapter_{chapter_num:02d}" / "chapter.mp3"
        if candidate.exists():
            chapter_mp3 = candidate
            break

    if chapter_mp3 is None:
        # Fallback: find any chapter.mp3 in the audio dir
        found = list(audio_dir.glob("**/chapter.mp3"))
        if found:
            chapter_mp3 = found[0]

    if chapter_mp3 is None:
        print("\nWARNING: Could not locate chapter.mp3 in the audio directory.", file=sys.stderr)
        print(f"Check {audio_dir}/ for generated audio files.", file=sys.stderr)
        duration = 0
        output_path = audio_dir / "chapter.mp3"
    else:
        # Copy the MP3 to the top-level output dir for easy access
        import shutil

        dest = output_dir / "chapter.mp3"
        shutil.copy2(chapter_mp3, dest)
        output_path = dest
        duration = _get_audio_duration_seconds(dest)
        logger.info("e2e_eval_audio_ready", output_path=str(dest), duration_seconds=duration)

    # Print the listening checklist
    checklist = format_checklist(output_path=output_path, duration_seconds=duration)
    print(checklist)

    sys.exit(0)


if __name__ == "__main__":
    main()
