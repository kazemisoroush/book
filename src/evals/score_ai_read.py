"""Scorer for the AI Read layer eval.

Runs golden-labeled passages through the real AISectionParser + LLM
and scores character detection, segment classification, and speaker
attribution against human-annotated ground truth.

Unlike the agent evals, this eval calls the AI directly — there is no
setup/agent/score cycle.  It runs end-to-end in a single command.

Requires AWS credentials configured (same as `make verify`).

Usage:
    python -m src.evals.score_ai_read
    python -m src.evals.score_ai_read --passage simple_dialogue
    python -m src.evals.score_ai_read --verbose
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
    Segment,
    SegmentType,
)
from src.parsers.ai_section_parser import AISectionParser

from src.evals.fixtures.golden_passages import ALL_PASSAGES, GoldenPassage

logger = structlog.get_logger(__name__)


def _find_segment_for_text(
    segments: list[Segment], substring: str
) -> Optional[Segment]:
    """Find the first dialogue segment whose text contains the substring."""
    needle = substring.lower()
    for seg in segments:
        if seg.is_dialogue() and needle in seg.text.lower():
            return seg
    return None


def _character_id_matches(actual: Optional[str], expected: str) -> bool:
    """Fuzzy match character IDs.

    The LLM might use slight variations: "mrs_bennet" vs "mrs-bennet"
    vs "mrsbennet".  We normalize by lowering and stripping separators.
    """
    if actual is None:
        return False
    def normalize(s: str) -> str:
        return s.lower().replace("_", "").replace("-", "").replace(" ", "")
    return normalize(actual) == normalize(expected)


def _run_passage(
    parser: AISectionParser,
    passage: GoldenPassage,
    verbose: bool = False,
) -> dict[str, list[tuple[str, str, bool]]]:
    """Run a single passage through the parser and score it.

    Returns a dict with keys "recall" and "precision", each containing
    a list of (check_name, description, passed) tuples.
    """
    registry = CharacterRegistry.with_default_narrator()
    scene_registry = SceneRegistry()
    section = Section(text=passage.text)

    segments, registry = parser.parse(
        section, registry, scene_registry=scene_registry
    )

    dialogue_segments = [s for s in segments if s.is_dialogue()]
    narration_segments = [s for s in segments if s.is_narration()]
    registry_ids = {c.character_id for c in registry.characters}

    recall: list[tuple[str, str, bool]] = []
    precision: list[tuple[str, str, bool]] = []

    # ── Recall: Character detection ───────────────────────────────────
    for expected_id in passage.expected_characters:
        found = any(_character_id_matches(rid, expected_id) for rid in registry_ids)
        recall.append((
            f"char-{expected_id}",
            f"Character '{expected_id}' detected",
            found,
        ))

    # ── Recall: Minimum dialogue segments ─────────────────────────────
    if passage.min_dialogue_segments > 0:
        enough_dialogue = len(dialogue_segments) >= passage.min_dialogue_segments
        recall.append((
            "min-dialogue",
            f"At least {passage.min_dialogue_segments} dialogue segments "
            f"(got {len(dialogue_segments)})",
            enough_dialogue,
        ))

    # ── Recall: Minimum narration segments ────────────────────────────
    if passage.min_narration_segments > 0:
        enough_narration = len(narration_segments) >= passage.min_narration_segments
        recall.append((
            "min-narration",
            f"At least {passage.min_narration_segments} narration segments "
            f"(got {len(narration_segments)})",
            enough_narration,
        ))

    # ── Recall: Speaker attribution ───────────────────────────────────
    for text_sub, expected_speaker in passage.expected_attributions:
        seg = _find_segment_for_text(segments, text_sub)
        if seg is None:
            # The text might have been split across segments — try broader match
            matched = False
            for s in dialogue_segments:
                if _character_id_matches(s.character_id, expected_speaker):
                    # Check if any word overlap
                    words = text_sub.lower().split()[:3]
                    if any(w in s.text.lower() for w in words):
                        matched = True
                        break
            recall.append((
                f"attr-{text_sub[:25]}",
                f"'{text_sub[:35]}...' → {expected_speaker}",
                matched,
            ))
        else:
            correct = _character_id_matches(seg.character_id, expected_speaker)
            recall.append((
                f"attr-{text_sub[:25]}",
                f"'{text_sub[:35]}...' → {expected_speaker}"
                + (f" (got {seg.character_id})" if not correct else ""),
                correct,
            ))

    # ── Precision: No hallucinated dialogue in pure narration ─────────
    if passage.min_dialogue_segments == 0 and not passage.expected_attributions:
        no_false_dialogue = len(dialogue_segments) == 0
        precision.append((
            "no-false-dialogue",
            f"No dialogue in pure narration passage (got {len(dialogue_segments)})",
            no_false_dialogue,
        ))

    # ── Precision: All segments have valid types ──────────────────────
    valid_types = all(
        s.segment_type in {SegmentType.DIALOGUE, SegmentType.NARRATION}
        for s in segments
    )
    precision.append((
        "valid-types",
        "All segments are dialogue or narration (narratable)",
        valid_types,
    ))

    # ── Precision: Dialogue segments have speakers ────────────────────
    if dialogue_segments:
        all_have_speakers = all(
            s.character_id is not None for s in dialogue_segments
        )
        precision.append((
            "speakers-assigned",
            "All dialogue segments have a character_id",
            all_have_speakers,
        ))

    # ── Precision: Narration attributed to narrator ───────────────────
    if narration_segments:
        narration_to_narrator = all(
            _character_id_matches(s.character_id, "narrator")
            for s in narration_segments
        )
        precision.append((
            "narration-narrator",
            "All narration segments attributed to narrator",
            narration_to_narrator,
        ))

    if verbose:
        print(f"\n  Segments returned ({len(segments)}):")
        for s in segments:
            print(
                f"    [{s.segment_type.value:10}] "
                f"[{s.character_id or '?':15}] "
                f"{s.text[:60]}..."
                if len(s.text) > 60
                else f"    [{s.segment_type.value:10}] "
                f"[{s.character_id or '?':15}] "
                f"{s.text}"
            )
        print(f"  Registry: {[c.character_id for c in registry.characters]}")

    return {"recall": recall, "precision": precision}


def run_eval(
    passage_name: Optional[str] = None,
    verbose: bool = False,
) -> None:
    """Run the AI Read eval against golden passages."""
    # Select passages
    if passage_name:
        passages = [p for p in ALL_PASSAGES if p.name == passage_name]
        if not passages:
            names = [p.name for p in ALL_PASSAGES]
            print(f"Unknown passage '{passage_name}'. Available: {names}")
            return
    else:
        passages = ALL_PASSAGES

    # Initialize real AI provider
    print("Initializing AI provider (AWS Bedrock)...")
    try:
        config = Config.from_env()
        ai_provider = AWSBedrockProvider(config)
    except Exception as e:
        print(f"ERROR: Could not initialize AI provider: {e}")
        print("Ensure AWS credentials are configured (same as `make verify`).")
        return

    from src.parsers.prompt_builder import PromptBuilder
    prompt_builder = PromptBuilder(
        book_title="Pride and Prejudice",
        book_author="Jane Austen",
    )
    parser = AISectionParser(ai_provider, prompt_builder=prompt_builder)

    # Run each passage
    all_recall: list[tuple[str, str, bool]] = []
    all_precision: list[tuple[str, str, bool]] = []

    print(f"\nRunning {len(passages)} passage(s)...\n")

    for passage in passages:
        print(f"── {passage.name} {'─' * (45 - len(passage.name))}")
        try:
            results = _run_passage(parser, passage, verbose=verbose)
        except Exception as e:
            print(f"  ERROR: {e}")
            # Count all checks as failed
            for expected_id in passage.expected_characters:
                all_recall.append((f"char-{expected_id}", str(e), False))
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
    print("AI READ EVAL RESULTS")
    print("=" * 55)
    print(f"\nRecall:    {passed_recall}/{total_recall}"
          f" ({passed_recall/total_recall:.0%})" if total_recall else "")
    print(f"Precision: {passed_precision}/{total_precision}"
          f" ({passed_precision/total_precision:.0%})" if total_precision else "")

    # For AI evals, we use a threshold rather than requiring 100%
    # because LLM output is non-deterministic
    recall_rate = passed_recall / total_recall if total_recall else 0
    precision_rate = passed_precision / total_precision if total_precision else 0
    threshold = 0.80

    print(f"\nThreshold: {threshold:.0%}")
    print(f"Score:     {'PASS' if recall_rate >= threshold and precision_rate >= threshold else 'FAIL'}")

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
    arg_parser = argparse.ArgumentParser(description="AI Read layer eval")
    arg_parser.add_argument(
        "--passage",
        type=str,
        default=None,
        help="Run a single passage by name (e.g. simple_dialogue)",
    )
    arg_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show full segment output for each passage",
    )
    args = arg_parser.parse_args()
    run_eval(passage_name=args.passage, verbose=args.verbose)
