"""Scorer for SOUND_EFFECT detection by the AI parser (US-023).

Runs golden-labeled passages through the real AISectionParser + LLM
and scores the AI's ability to:
  - Detect explicit diegetic sound events as SOUND_EFFECT segments (recall)
  - Avoid hallucinating sounds where none are mentioned (precision)
  - Set correct fields on SOUND_EFFECT segments (precision)

Unlike the agent evals, this eval calls the AI directly — there is no
setup/agent/score cycle.  It runs end-to-end in a single command.

Requires AWS credentials configured (same as ``make verify``).

Usage:
    python -m src.evals.book.score_sound_effect_detection
    python -m src.evals.book.score_sound_effect_detection --passage explicit_sounds
    python -m src.evals.book.score_sound_effect_detection --verbose
"""
import argparse
from typing import Optional

import structlog

from src.ai.aws_bedrock_provider import AWSBedrockProvider
from src.config.config import Config
from src.domain.models import (
    CharacterRegistry,
    SceneRegistry,
    Section,
    SegmentType,
)
from src.evals.fixtures.golden_sound_effect_passages import ALL_SOUND_EFFECT_PASSAGES, GoldenSoundEffectPassage
from src.parsers.ai_section_parser import AISectionParser
from src.parsers.prompt_builder import PromptBuilder

logger = structlog.get_logger(__name__)


def _sound_effect_label_matches(segment_text: str, expected_label: str) -> bool:
    """Fuzzy match a SOUND_EFFECT segment's text against an expected label.

    The AI might use variations: "dog howling" vs "howl" vs "howling dogs".
    We check if the expected label (or its stem) appears as a substring
    of the segment text, case-insensitive.
    """
    needle = expected_label.lower()
    haystack = segment_text.lower()
    # Direct substring match
    if needle in haystack:
        return True
    # Try common variations: strip trailing s/ing/ed
    for suffix in ("ing", "ed", "s"):
        stem = needle.rstrip(suffix) if needle.endswith(suffix) else needle
        if len(stem) >= 3 and stem in haystack:
            return True
    return False


def _run_passage(
    parser: AISectionParser,
    passage: GoldenSoundEffectPassage,
    verbose: bool = False,
) -> dict[str, list[tuple[str, str, bool]]]:
    """Run a single passage through the parser and score sound effect detection.

    Returns a dict with keys "recall" and "precision", each containing
    a list of (check_name, description, passed) tuples.
    """
    registry = CharacterRegistry.with_default_narrator()
    scene_registry = SceneRegistry()
    section = Section(text=passage.text)

    segments, registry = parser.parse(
        section, registry, scene_registry=scene_registry
    )

    sound_effect_segments = [
        s for s in segments if s.segment_type == SegmentType.SOUND_EFFECT
    ]

    recall: list[tuple[str, str, bool]] = []
    precision: list[tuple[str, str, bool]] = []

    # ── Recall: Expected sound effect labels detected ──────────────────
    for label in passage.expected_sound_effect_labels:
        found = any(_sound_effect_label_matches(s.text, label) for s in sound_effect_segments)
        # Also check sound_effect_detail field
        if not found:
            found = any(
                s.sound_effect_detail is not None
                and _sound_effect_label_matches(s.sound_effect_detail, label)
                for s in sound_effect_segments
            )
        recall.append((
            f"sound-effect-{label}",
            f"Sound '{label}' detected as SOUND_EFFECT segment",
            found,
        ))

    # ── Recall: Minimum sound effect segment count ─────────────────────
    if passage.min_sound_effect_segments > 0:
        enough_sound_effects = len(sound_effect_segments) >= passage.min_sound_effect_segments
        recall.append((
            "min-sound-effects",
            f"At least {passage.min_sound_effect_segments} SOUND_EFFECT segments "
            f"(got {len(sound_effect_segments)})",
            enough_sound_effects,
        ))

    # ── Precision: No hallucinated sound effects in passages with no sounds
    if passage.expect_no_sound_effects:
        no_false_sound_effects = len(sound_effect_segments) == 0
        precision.append((
            "no-false-sound-effects",
            f"No SOUND_EFFECT in passage with no explicit sounds "
            f"(got {len(sound_effect_segments)})",
            no_false_sound_effects,
        ))

    # ── Precision: All sound effect segments have character_id=None ────
    if sound_effect_segments:
        all_null_character = all(
            s.character_id is None for s in sound_effect_segments
        )
        precision.append((
            "sound-effect-no-character",
            "All SOUND_EFFECT segments have character_id=None",
            all_null_character,
        ))

    # ── Precision: All sound effect segments have non-empty text ───────
    if sound_effect_segments:
        all_have_text = all(
            s.text.strip() != "" for s in sound_effect_segments
        )
        precision.append((
            "sound-effect-has-text",
            "All SOUND_EFFECT segments have non-empty text label",
            all_have_text,
        ))

    if verbose:
        print(f"\n  All segments ({len(segments)}):")
        for s in segments:
            detail = ""
            if s.segment_type == SegmentType.SOUND_EFFECT:
                detail = f" [detail: {s.sound_effect_detail or '(none)'}]"
            label = s.text[:60] + "..." if len(s.text) > 60 else s.text
            print(
                f"    [{s.segment_type.value:12}] "
                f"[{s.character_id or '(none)':15}] "
                f"{label}{detail}"
            )
        print(f"  SOUND_EFFECT segments: {len(sound_effect_segments)}")

    return {"recall": recall, "precision": precision}


def run_eval(
    passage_name: Optional[str] = None,
    verbose: bool = False,
) -> None:
    """Run the sound effect detection eval against golden passages."""
    # Select passages
    if passage_name:
        passages = [p for p in ALL_SOUND_EFFECT_PASSAGES if p.name == passage_name]
        if not passages:
            names = [p.name for p in ALL_SOUND_EFFECT_PASSAGES]
            print(f"Unknown passage '{passage_name}'. Available: {names}")
            return
    else:
        passages = ALL_SOUND_EFFECT_PASSAGES

    # Initialize real AI provider
    print("Initializing AI provider (AWS Bedrock)...")
    try:
        config = Config.from_env()
        ai_provider = AWSBedrockProvider(config)
    except Exception as e:
        print(f"ERROR: Could not initialize AI provider: {e}")
        print("Ensure AWS credentials are configured (same as `make verify`).")
        return

    # Run each passage
    all_recall: list[tuple[str, str, bool]] = []
    all_precision: list[tuple[str, str, bool]] = []

    print(f"\nRunning {len(passages)} passage(s)...\n")

    for passage in passages:
        print(f"── {passage.name} {'─' * (45 - len(passage.name))}")

        prompt_builder = PromptBuilder(
            book_title=passage.book_title,
            book_author=passage.book_author,
        )
        parser = AISectionParser(ai_provider, prompt_builder=prompt_builder)

        try:
            results = _run_passage(parser, passage, verbose=verbose)
        except Exception as e:
            print(f"  ERROR: {e}")
            for label in passage.expected_sound_effect_labels:
                all_recall.append((f"sound-effect-{label}", str(e), False))
            continue

        for tag, desc, ok in results["recall"]:
            status = "PASS" if ok else "FAIL"
            print(f"  {status}  {desc}")
            all_recall.append((f"{passage.name}/{tag}", desc, ok))

        for tag, desc, ok in results["precision"]:
            status = "PASS" if ok else "FAIL"
            print(f"  {status}  {desc}")
            all_precision.append((f"{passage.name}/{tag}", desc, ok))

    # ── Summary ───────────────────────────────────────────────────────
    total_recall = len(all_recall)
    passed_recall = sum(1 for _, _, ok in all_recall if ok)
    total_precision = len(all_precision)
    passed_precision = sum(1 for _, _, ok in all_precision if ok)

    print()
    print("=" * 55)
    print("SOUND EFFECT DETECTION EVAL RESULTS")
    print("=" * 55)
    if total_recall:
        print(
            f"\nRecall:    {passed_recall}/{total_recall}"
            f" ({passed_recall / total_recall:.0%})"
        )
    if total_precision:
        print(
            f"Precision: {passed_precision}/{total_precision}"
            f" ({passed_precision / total_precision:.0%})"
        )

    recall_rate = passed_recall / total_recall if total_recall else 0
    precision_rate = passed_precision / total_precision if total_precision else 0
    threshold = 0.80

    print(f"\nThreshold: {threshold:.0%}")
    passed = recall_rate >= threshold and precision_rate >= threshold
    print(f"Score:     {'PASS' if passed else 'FAIL'}")

    if recall_rate < threshold:
        print("\n  Recall failures:")
        for tag, desc, ok in all_recall:
            if not ok:
                print(f"    FAIL  {tag}: {desc}")

    if precision_rate < threshold:
        print("\n  Precision failures:")
        for tag, desc, ok in all_precision:
            if not ok:
                print(f"    FAIL  {tag}: {desc}")


if __name__ == "__main__":
    arg_parser = argparse.ArgumentParser(
        description="Sound effect detection eval (US-023)"
    )
    arg_parser.add_argument(
        "--passage",
        type=str,
        default=None,
        help="Run a single passage by name (e.g. explicit_sounds)",
    )
    arg_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show full segment output for each passage",
    )
    args = arg_parser.parse_args()
    run_eval(passage_name=args.passage, verbose=args.verbose)
