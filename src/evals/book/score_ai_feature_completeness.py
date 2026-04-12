"""Scorer for AI feature completeness (EV-006).

Runs golden-labeled passages through the real AISectionParser + LLM
and scores the AI's ability to emit all supported features:
  - Segment types: narration, dialogue, sound_effect, vocal_effect
  - Emotion tags on dialogue segments
  - Scene detection (scene_id assigned)
  - Voice settings populated (voice_stability, voice_style, voice_speed)
  - Precision: no hallucinated sound effects or vocal effects in quiet passages

Unlike the agent evals, this eval calls the AI directly — there is no
setup/agent/score cycle.  It runs end-to-end in a single command.

Requires AWS credentials configured (same as ``make verify``).

Cost: ~$0.10-$0.30 per passage ($0.40-$1.20 for all 4 passages).

Usage:
    python -m src.evals.book.score_ai_feature_completeness
    python -m src.evals.book.score_ai_feature_completeness --passage feature_rich
    python -m src.evals.book.score_ai_feature_completeness --verbose
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
from src.evals.book.fixtures.golden_feature_passages import (
    ALL_FEATURE_PASSAGES,
    GoldenFeaturePassage,
)
from src.parsers.ai_section_parser import AISectionParser
from src.parsers.prompt_builder import PromptBuilder

logger = structlog.get_logger(__name__)


def _fuzzy_emotion_match(segment_emotion: str, expected: str) -> bool:
    """Fuzzy match a segment's emotion against an expected label.

    Checks if the expected label (or a stem) appears as a substring
    of the segment's emotion, case-insensitive. For example, "fear"
    matches "fearful", "afraid" is not matched but "fear" in "fearful" is.
    """
    needle = expected.lower()
    haystack = segment_emotion.lower()
    if needle in haystack:
        return True
    # Try common variations
    for suffix in ("ing", "ed", "s", "ful", "ous"):
        stem = needle.rstrip(suffix) if needle.endswith(suffix) else needle
        if len(stem) >= 3 and stem in haystack:
            return True
    return False


def _fuzzy_label_match(segment_text: str, expected_label: str) -> bool:
    """Fuzzy match a segment's text against an expected label."""
    needle = expected_label.lower()
    haystack = segment_text.lower()
    if needle in haystack:
        return True
    for suffix in ("ing", "ed", "s"):
        stem = needle.rstrip(suffix) if needle.endswith(suffix) else needle
        if len(stem) >= 3 and stem in haystack:
            return True
    return False


def _run_passage(
    parser: AISectionParser,
    passage: GoldenFeaturePassage,
    verbose: bool = False,
) -> dict[str, list[tuple[str, str, bool]]]:
    """Run a single passage through the parser and score feature completeness."""
    registry = CharacterRegistry.with_default_narrator()
    scene_registry = SceneRegistry()
    section = Section(text=passage.text)

    segments, registry = parser.parse(
        section, registry, scene_registry=scene_registry
    )

    recall: list[tuple[str, str, bool]] = []
    precision: list[tuple[str, str, bool]] = []

    # Group segments by type
    type_counts: dict[str, int] = {}
    for s in segments:
        type_counts[s.segment_type.value] = type_counts.get(s.segment_type.value, 0) + 1

    # ── Recall: Expected segment types present ────────────────────────
    for expected_type in passage.expected_segment_types:
        found = type_counts.get(expected_type, 0) > 0
        recall.append((
            f"type-{expected_type}",
            f"At least one {expected_type} segment emitted",
            found,
        ))

    # ── Recall: Minimum segment counts ────────────────────────────────
    for seg_type, min_count in passage.min_segment_counts.items():
        actual = type_counts.get(seg_type, 0)
        enough = actual >= min_count
        recall.append((
            f"min-{seg_type}",
            f"At least {min_count} {seg_type} segments (got {actual})",
            enough,
        ))

    # ── Recall: Expected emotions detected ────────────────────────────
    for expected_emotion in passage.expected_emotions:
        found = any(
            s.emotion is not None and _fuzzy_emotion_match(s.emotion, expected_emotion)
            for s in segments
        )
        recall.append((
            f"emotion-{expected_emotion}",
            f"Emotion '{expected_emotion}' detected on at least one segment",
            found,
        ))

    # ── Recall: Scene detection ───────────────────────────────────────
    if passage.expect_scene:
        has_scene = scene_registry.all() != []
        recall.append((
            "scene-detected",
            "At least one scene detected in scene_registry",
            has_scene,
        ))

    # ── Recall: Expected vocal effect labels ──────────────────────────
    vocal_segments = [
        s for s in segments if s.segment_type == SegmentType.VOCAL_EFFECT
    ]
    for label in passage.expected_vocal_effect_labels:
        found = any(_fuzzy_label_match(s.text, label) for s in vocal_segments)
        recall.append((
            f"vocal-{label}",
            f"Vocal effect '{label}' detected as VOCAL_EFFECT segment",
            found,
        ))

    # ── Recall: Voice settings populated ──────────────────────────────
    narratable = [
        s for s in segments
        if s.segment_type in {SegmentType.DIALOGUE, SegmentType.NARRATION}
    ]
    if narratable:
        has_stability = any(s.voice_stability is not None for s in narratable)
        has_style = any(s.voice_style is not None for s in narratable)
        has_speed = any(s.voice_speed is not None for s in narratable)
        recall.append((
            "voice-stability",
            "At least one narratable segment has voice_stability set",
            has_stability,
        ))
        recall.append((
            "voice-style",
            "At least one narratable segment has voice_style set",
            has_style,
        ))
        recall.append((
            "voice-speed",
            "At least one narratable segment has voice_speed set",
            has_speed,
        ))

    # ── Precision: No hallucinated sound effects ──────────────────────
    sfx_segments = [
        s for s in segments if s.segment_type == SegmentType.SOUND_EFFECT
    ]
    if passage.expect_no_sound_effects:
        precision.append((
            "no-false-sound-effects",
            f"No SOUND_EFFECT in quiet passage (got {len(sfx_segments)})",
            len(sfx_segments) == 0,
        ))

    # ── Precision: No hallucinated vocal effects ──────────────────────
    if passage.expect_no_vocal_effects:
        precision.append((
            "no-false-vocal-effects",
            f"No VOCAL_EFFECT in quiet passage (got {len(vocal_segments)})",
            len(vocal_segments) == 0,
        ))

    # ── Precision: SOUND_EFFECT segments have character_id=None ───────
    if sfx_segments:
        all_null = all(s.character_id is None for s in sfx_segments)
        precision.append((
            "sfx-no-character",
            "All SOUND_EFFECT segments have character_id=None",
            all_null,
        ))

    # ── Precision: Dialogue segments have character_id set ────────────
    dialogue_segments = [
        s for s in segments if s.segment_type == SegmentType.DIALOGUE
    ]
    if dialogue_segments:
        all_have_speaker = all(
            s.character_id is not None for s in dialogue_segments
        )
        precision.append((
            "dialogue-has-speaker",
            "All DIALOGUE segments have a non-null character_id",
            all_have_speaker,
        ))

    if verbose:
        print(f"\n  All segments ({len(segments)}):")
        for s in segments:
            extras = []
            if s.emotion and s.emotion != "neutral":
                extras.append(f"emotion={s.emotion}")
            if s.voice_stability is not None:
                extras.append(f"stab={s.voice_stability}")
            if s.segment_type == SegmentType.SOUND_EFFECT and s.sound_effect_detail:
                extras.append(f"detail={s.sound_effect_detail}")
            extra_str = f" [{', '.join(extras)}]" if extras else ""
            label = s.text[:55] + "..." if len(s.text) > 55 else s.text
            print(
                f"    [{s.segment_type.value:12}] "
                f"[{s.character_id or '(none)':15}] "
                f"{label}{extra_str}"
            )
        print(f"  Type counts: {type_counts}")
        print(f"  Scenes: {len(scene_registry.all())}")

    return {"recall": recall, "precision": precision}


def run_eval(
    passage_name: Optional[str] = None,
    verbose: bool = False,
) -> None:
    """Run the AI feature completeness eval against golden passages."""
    if passage_name:
        passages = [p for p in ALL_FEATURE_PASSAGES if p.name == passage_name]
        if not passages:
            names = [p.name for p in ALL_FEATURE_PASSAGES]
            print(f"Unknown passage '{passage_name}'. Available: {names}")
            return
    else:
        passages = ALL_FEATURE_PASSAGES

    print("Initializing AI provider (AWS Bedrock)...")
    try:
        config = Config.from_env()
        ai_provider = AWSBedrockProvider(config)
    except Exception as e:
        print(f"ERROR: Could not initialize AI provider: {e}")
        print("Ensure AWS credentials are configured (same as `make verify`).")
        return

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
            for st in passage.expected_segment_types:
                all_recall.append((f"{passage.name}/type-{st}", str(e), False))
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
    print("AI FEATURE COMPLETENESS EVAL RESULTS")
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
        description="AI feature completeness eval (EV-006)"
    )
    arg_parser.add_argument(
        "--passage",
        type=str,
        default=None,
        help="Run a single passage by name (e.g. feature_rich)",
    )
    arg_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show full segment output for each passage",
    )
    args = arg_parser.parse_args()
    run_eval(passage_name=args.passage, verbose=args.verbose)
