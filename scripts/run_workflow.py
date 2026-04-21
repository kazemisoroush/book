"""Dispatch shim — run a book-processing workflow from the command line.

Usage:
    python scripts/run_workflow.py --workflow ai --url URL
    python scripts/run_workflow.py --workflow tts --url URL
    python scripts/run_workflow.py --workflow eval-best --passage dracula_arrival
    python scripts/run_workflow.py --workflow eval-free --passage dracula_arrival --device cuda

Examples:
    # Parse all chapters (auto-resumes from cache if it exists)
    python scripts/run_workflow.py --url https://www.gutenberg.org/cache/epub/1342/pg1342-h.zip

    # Parse only chapters 5-15
    python scripts/run_workflow.py --url URL --start-chapter 5 --end-chapter 15

    # Run TTS workflow
    python scripts/run_workflow.py --url URL --workflow tts

    # Run paid eval (Fish Audio + Stable Audio)
    python scripts/run_workflow.py --workflow eval-best --passage dracula_arrival

    # Run free eval (VibeVoice + AudioCraft, local inference)
    python scripts/run_workflow.py --workflow eval-free --passage dracula_arrival --device cuda
"""
import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Union

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)

from src.config.logging_config import configure as configure_logging  # noqa: E402

configure_logging()

import structlog  # noqa: E402

logger = structlog.get_logger(__name__)

ALL_WORKFLOWS = ["parse", "ai", "tts", "ambient", "sfx", "music", "mix", "eval-best", "eval-free"]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a book-processing workflow.",
    )
    parser.add_argument(
        "--workflow",
        choices=ALL_WORKFLOWS,
        default="ai",
        help="Workflow to run (default: ai)",
    )

    # ── Gutenberg workflows (parse / ai / tts) ───────────────────────
    parser.add_argument("--url", default=None, help="Project Gutenberg zip URL (required for parse/ai/tts)")
    parser.add_argument("--start-chapter", type=int, default=1, help="1-based start chapter (default: 1)")
    parser.add_argument("--end-chapter", type=int, default=None, help="1-based end chapter (inclusive)")
    parser.add_argument("--refresh", action="store_true", default=False, help="Bypass cache and re-run the workflow stage from scratch")
    parser.add_argument("--debug", action="store_true", default=False, help="Keep individual segment MP3 files")

    # ── Eval workflows (eval-best / eval-free) ───────────────────────
    parser.add_argument("--passage", metavar="NAME", default=None,
                        help="Named golden passage (e.g. 'dracula_arrival'). Required for eval workflows.")
    parser.add_argument("--output-dir", metavar="DIR", default="evals_output",
                        help="Base directory for eval output (default: evals_output)")
    parser.add_argument("--device", metavar="DEVICE", default="cpu",
                        help="PyTorch device for eval-free models (cpu, cuda, mps). Default: cpu.")
    parser.add_argument("--tts-model", metavar="MODEL", default="microsoft/VibeVoice-Realtime-0.5B",
                        help="HuggingFace model for VibeVoice TTS (eval-free only).")
    parser.add_argument("--audiogen-model", metavar="MODEL", default="facebook/audiogen-medium",
                        help="HuggingFace model for AudioGen (eval-free only).")
    parser.add_argument("--musicgen-model", metavar="MODEL", default="facebook/musicgen-small",
                        help="HuggingFace model for MusicGen (eval-free only).")

    # ── Feature flags (tts / eval workflows) ─────────────────────────
    parser.add_argument("--enable-ambient", action="store_true", help="Enable ambient background sound")
    parser.add_argument("--disable-ambient", action="store_true", help="Disable ambient background sound")
    parser.add_argument("--enable-sound-effects", action="store_true", help="Enable sound effects")
    parser.add_argument("--disable-sound-effects", action="store_true", help="Disable sound effects")
    parser.add_argument("--enable-emotion", action="store_true", help="Enable emotion tags")
    parser.add_argument("--disable-emotion", action="store_true", help="Disable emotion tags")
    parser.add_argument("--enable-voice-design", action="store_true", help="Enable voice design")
    parser.add_argument("--disable-voice-design", action="store_true", help="Disable voice design")
    parser.add_argument("--enable-scene-context", action="store_true", help="Enable scene context")
    parser.add_argument("--disable-scene-context", action="store_true", help="Disable scene context")

    args = parser.parse_args()

    # ── Validate required args per workflow ───────────────────────────
    if args.workflow in ("parse", "ai", "tts", "ambient", "sfx", "music", "mix") and not args.url:
        parser.error(f"--url is required for --workflow {args.workflow}")
    if args.workflow in ("eval-best", "eval-free") and not args.passage:
        parser.error(f"--passage is required for --workflow {args.workflow}")

    # ── Dispatch ──────────────────────────────────────────────────────
    if args.workflow in ("eval-best", "eval-free"):
        _run_eval(args)
    else:
        _run_gutenberg(args)


def _run_gutenberg(args: argparse.Namespace) -> None:
    """Dispatch parse / ai / tts / ambient / sfx / music / mix workflows."""
    from src.workflows.project_gutenberg_workflow import ProjectGutenbergWorkflow
    from src.workflows.ai_project_gutenberg_workflow import AIProjectGutenbergWorkflow
    from src.workflows.tts_workflow import TTSWorkflow
    from src.workflows.ambient_workflow import AmbientWorkflow
    from src.workflows.sfx_workflow import SfxWorkflow
    from src.workflows.music_workflow import MusicWorkflow
    from src.workflows.mix_workflow import MixWorkflow
    from src.repository.file_book_repository import FileBookRepository

    workflow: Union[
        ProjectGutenbergWorkflow,
        AIProjectGutenbergWorkflow,
        TTSWorkflow,
        AmbientWorkflow,
        SfxWorkflow,
        MusicWorkflow,
        MixWorkflow,
    ]

    if args.workflow == "parse":
        workflow = ProjectGutenbergWorkflow.create()
    elif args.workflow == "ai":
        repository = FileBookRepository()
        workflow = AIProjectGutenbergWorkflow.create(repository=repository)
    elif args.workflow == "tts":
        workflow = TTSWorkflow.create()
    elif args.workflow == "ambient":
        workflow = AmbientWorkflow.create()
    elif args.workflow == "sfx":
        workflow = SfxWorkflow.create()
    elif args.workflow == "music":
        workflow = MusicWorkflow.create()
    elif args.workflow == "mix":
        workflow = MixWorkflow.create()
    else:
        raise ValueError(f"Unknown workflow: {args.workflow}")

    logger.info(
        "run_workflow_start",
        workflow=args.workflow,
        url=args.url,
        start_chapter=args.start_chapter,
        end_chapter=args.end_chapter,
    )

    run_kwargs: dict[str, object] = {}

    if args.workflow == "ai":
        run_kwargs["start_chapter"] = args.start_chapter
        if args.end_chapter is not None:
            run_kwargs["end_chapter"] = args.end_chapter
        if args.refresh:
            run_kwargs["refresh"] = True

    if args.debug:
        run_kwargs["debug"] = True

    run_kwargs.update(_resolve_feature_flags(args))

    workflow.run(args.url, **run_kwargs)  # type: ignore[arg-type]

    logger.info("run_workflow_done")
    print("Done", file=sys.stderr)


def _run_eval(args: argparse.Namespace) -> None:
    """Dispatch eval-best / eval-free workflows."""
    from src.config.feature_flags import FeatureFlags
    from src.repository.book_id import generate_book_id
    from src.workflows.listening_eval_workflow import (
        ListeningEvalWorkflow,
        _CHECKLIST_FEATURES,
        _get_audio_duration_seconds,
        _resolve_passage,
    )

    passage = _resolve_passage(args.passage)

    now = datetime.utcnow()
    tag = "e2e" if args.workflow == "eval-best" else "e2e-free"
    output_dir = Path(args.output_dir) / f"{tag}-{now.strftime('%Y-%m-%d-%H%M%S')}"
    output_dir.mkdir(parents=True, exist_ok=True)

    feature_flags = FeatureFlags(
        ambient_enabled=True,
        sound_effects_enabled=True,
        emotion_enabled=True,
        voice_design_enabled=True,
        scene_context_enabled=True,
        chapter_announcer_enabled=True,
    )

    books_dir = output_dir / "books"

    if args.workflow == "eval-best":
        print("\nRunning E2E listening eval (Fish Audio + Stable Audio)...")
        first_chapter = passage.book.content.chapters[0]
        print(f"Passage: {passage.name} ({passage.book.metadata.title}, Chapter {first_chapter.number})")
        print(f"Output:  {output_dir}/\n")

        workflow = ListeningEvalWorkflow.create(books_dir=books_dir)
        book = workflow.run(passage=passage, debug=args.debug, feature_flags=feature_flags)
        cost_line = "Cost estimate: $2.50 - $5.00 (varies by passage length and features used)"
    else:  # eval-free
        from src.workflows.listening_eval_free_workflow import ListeningEvalFreeWorkflow

        print("\nRunning FREE E2E listening eval (VibeVoice TTS + AudioCraft)...")
        first_chapter = passage.book.content.chapters[0]
        print(f"Passage:       {passage.name} ({passage.book.metadata.title}, Chapter {first_chapter.number})")
        print(f"Device:        {args.device}")
        print(f"TTS model:     {args.tts_model}")
        print(f"AudioGen:      {args.audiogen_model}")
        print(f"MusicGen:      {args.musicgen_model}")
        print(f"Output:        {output_dir}/")
        print("Cost:          $0.00 (local inference only)\n")

        workflow = ListeningEvalFreeWorkflow.create(  # type: ignore[assignment]
            books_dir=books_dir,
            device=args.device,
            tts_model=args.tts_model,
            audiogen_model=args.audiogen_model,
            musicgen_model=args.musicgen_model,
        )
        book = workflow.run(passage=passage, debug=args.debug, feature_flags=feature_flags)
        cost_line = "Cost: $0.00 (VibeVoice TTS + AudioCraft, local inference)"

    # Locate and copy the generated chapter MP3
    chapter = book.content.chapters[0]
    book_id = generate_book_id(book.metadata)
    audio_dir = books_dir / book_id / "audio"
    chapter_mp3 = audio_dir / f"chapter_{chapter.number:02d}" / "chapter.mp3"

    if not chapter_mp3.exists():
        found = list(audio_dir.glob("**/chapter.mp3"))
        chapter_mp3 = found[0] if found else None  # type: ignore[assignment]

    if chapter_mp3 is None or not chapter_mp3.exists():
        print(f"\nWARNING: Could not locate chapter.mp3 in {audio_dir}/", file=sys.stderr)
        output_path = audio_dir / "chapter.mp3"
        duration = 0
    else:
        dest = output_dir / "chapter.mp3"
        shutil.copy2(chapter_mp3, dest)
        output_path = dest
        duration = _get_audio_duration_seconds(dest)

    # Print listening checklist
    minutes, secs = divmod(duration, 60)
    border = "\u2550" * 62
    label = "E2E LISTENING EVAL" if args.workflow == "eval-best" else "E2E LISTENING EVAL (Free)"
    print(f"\n{border}")
    print(f"{label} \u2014 Generated audio ready for review")
    print(f"{border}\n")
    print(f"Output: {output_path}")
    print(f"Duration: {minutes}:{secs:02d}\n")
    print("Listen for the following features:\n")
    for feat in _CHECKLIST_FEATURES:
        print(f"[ ] {feat}")
    print(f"\n{cost_line}\n")


def _resolve_feature_flags(args: argparse.Namespace) -> dict[str, object]:
    """Build feature flag kwargs from --enable/--disable CLI flags."""
    kwargs: dict[str, object] = {}

    def resolve(enable: bool, disable: bool) -> bool:
        if disable:
            return False
        if enable:
            return True
        return True  # Default enabled

    if args.disable_ambient or args.enable_ambient:
        kwargs["ambient_enabled"] = resolve(args.enable_ambient, args.disable_ambient)
    if args.disable_sound_effects or args.enable_sound_effects:
        kwargs["sound_effects_enabled"] = resolve(args.enable_sound_effects, args.disable_sound_effects)
    if args.disable_emotion or args.enable_emotion:
        kwargs["emotion_enabled"] = resolve(args.enable_emotion, args.disable_emotion)
    if args.disable_voice_design or args.enable_voice_design:
        kwargs["voice_design_enabled"] = resolve(args.enable_voice_design, args.disable_voice_design)
    if args.disable_scene_context or args.enable_scene_context:
        kwargs["scene_context_enabled"] = resolve(args.enable_scene_context, args.disable_scene_context)

    return kwargs


if __name__ == "__main__":
    main()
