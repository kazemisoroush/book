"""Scorer for the Announcement Formatter eval.

Runs golden-labeled book title and chapter announcement cases through the
real AnnouncementFormatter + LLM and scores output quality against
human-annotated expected/forbidden substrings.

Requires AWS credentials configured (same as ``make verify``).

Usage:
    python -m src.evals.book.score_announcements
    python -m src.evals.book.score_announcements --verbose
"""
import argparse

import structlog

from src.ai.aws_bedrock_provider import AWSBedrockProvider
from src.config.config import Config
from src.parsers.announcement_formatter import AnnouncementFormatter

from src.evals.book.fixtures.golden_announcements import (
    ALL_BOOK_TITLES,
    ALL_CHAPTER_ANNOUNCEMENTS,
    GoldenBookTitle,
    GoldenChapterAnnouncement,
)

logger = structlog.get_logger(__name__)


def _score_book_title(
    formatter: AnnouncementFormatter,
    case: GoldenBookTitle,
    verbose: bool = False,
) -> dict[str, list[tuple[str, str, bool]]]:
    """Score a single book title formatting case."""
    formatted = formatter.format_book_title(case.raw_title, case.raw_author)

    if verbose:
        print(f"  Input:  title={case.raw_title!r}, author={case.raw_author!r}")
        print(f"  Output: {formatted!r}")

    recall: list[tuple[str, str, bool]] = []
    precision: list[tuple[str, str, bool]] = []

    # Recall: expected substrings must appear
    for sub in case.expected_substrings:
        found = sub.lower() in formatted.lower()
        recall.append((
            f"contains-{sub[:20]}",
            f"Output contains '{sub}'",
            found,
        ))

    # Precision: forbidden substrings must not appear
    for sub in case.forbidden_substrings:
        absent = sub.lower() not in formatted.lower()
        precision.append((
            f"excludes-{sub[:20]}",
            f"Output excludes '{sub}'",
            absent,
        ))

    # Precision: output should be reasonably short (< 200 chars)
    short_enough = len(formatted) < 200
    precision.append((
        "length",
        f"Output under 200 chars (got {len(formatted)})",
        short_enough,
    ))

    return {"recall": recall, "precision": precision}


def _score_chapter_announcement(
    formatter: AnnouncementFormatter,
    case: GoldenChapterAnnouncement,
    verbose: bool = False,
) -> dict[str, list[tuple[str, str, bool]]]:
    """Score a single chapter announcement formatting case."""
    formatted = formatter.format_chapter_announcement(case.chapter_number, case.chapter_title)

    if verbose:
        print(f"  Input:  number={case.chapter_number}, title={case.chapter_title!r}")
        print(f"  Output: {formatted!r}")

    recall: list[tuple[str, str, bool]] = []
    precision: list[tuple[str, str, bool]] = []

    # Recall: expected substrings must appear
    for sub in case.expected_substrings:
        found = sub.lower() in formatted.lower()
        recall.append((
            f"contains-{sub[:20]}",
            f"Output contains '{sub}'",
            found,
        ))

    # Precision: forbidden substrings must not appear
    for sub in case.forbidden_substrings:
        absent = sub.lower() not in formatted.lower()
        precision.append((
            f"excludes-{sub[:20]}",
            f"Output excludes '{sub}'",
            absent,
        ))

    # Precision: output should be short (< 150 chars)
    short_enough = len(formatted) < 150
    precision.append((
        "length",
        f"Output under 150 chars (got {len(formatted)})",
        short_enough,
    ))

    return {"recall": recall, "precision": precision}


def run_eval(verbose: bool = False) -> None:
    """Run the Announcement Formatter eval."""
    print("Initializing AI provider (AWS Bedrock)...")
    try:
        config = Config.from_env()
        ai_provider = AWSBedrockProvider(config)
    except Exception as e:
        print(f"ERROR: Could not initialize AI provider: {e}")
        print("Ensure AWS credentials are configured (same as `make verify`).")
        return

    formatter = AnnouncementFormatter(ai_provider)

    all_recall: list[tuple[str, str, bool]] = []
    all_precision: list[tuple[str, str, bool]] = []

    # ── Book titles ──────────────────────────────────────────────────
    print(f"\n{'=' * 55}")
    print(f"BOOK TITLES ({len(ALL_BOOK_TITLES)} cases)")
    print(f"{'=' * 55}\n")

    for case in ALL_BOOK_TITLES:
        print(f"── {case.name} {'─' * (45 - len(case.name))}")
        try:
            results = _score_book_title(formatter, case, verbose=verbose)
        except Exception as e:
            print(f"  ERROR: {e}")
            continue

        for tag, desc, ok in results["recall"]:
            print(f"  {'PASS' if ok else 'FAIL'}  {desc}")
            all_recall.append((f"title/{case.name}/{tag}", desc, ok))
        for tag, desc, ok in results["precision"]:
            print(f"  {'PASS' if ok else 'FAIL'}  {desc}")
            all_precision.append((f"title/{case.name}/{tag}", desc, ok))

    # ── Chapter announcements ────────────────────────────────────────
    print(f"\n{'=' * 55}")
    print(f"CHAPTER ANNOUNCEMENTS ({len(ALL_CHAPTER_ANNOUNCEMENTS)} cases)")
    print(f"{'=' * 55}\n")

    for ch_case in ALL_CHAPTER_ANNOUNCEMENTS:
        print(f"── {ch_case.name} {'─' * (45 - len(ch_case.name))}")
        try:
            results = _score_chapter_announcement(formatter, ch_case, verbose=verbose)
        except Exception as e:
            print(f"  ERROR: {e}")
            continue

        for tag, desc, ok in results["recall"]:
            print(f"  {'PASS' if ok else 'FAIL'}  {desc}")
            all_recall.append((f"chapter/{ch_case.name}/{tag}", desc, ok))
        for tag, desc, ok in results["precision"]:
            print(f"  {'PASS' if ok else 'FAIL'}  {desc}")
            all_precision.append((f"chapter/{ch_case.name}/{tag}", desc, ok))

    # ── Summary ──────────────────────────────────────────────────────
    total_recall = len(all_recall)
    passed_recall = sum(1 for _, _, ok in all_recall if ok)
    total_precision = len(all_precision)
    passed_precision = sum(1 for _, _, ok in all_precision if ok)

    print()
    print("=" * 55)
    print("ANNOUNCEMENT FORMATTER EVAL RESULTS")
    print("=" * 55)
    if total_recall:
        print(f"\nRecall:    {passed_recall}/{total_recall}"
              f" ({passed_recall / total_recall:.0%})")
    if total_precision:
        print(f"Precision: {passed_precision}/{total_precision}"
              f" ({passed_precision / total_precision:.0%})")

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
    arg_parser = argparse.ArgumentParser(description="Announcement Formatter eval")
    arg_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show raw input/output for each case",
    )
    args = arg_parser.parse_args()
    run_eval(verbose=args.verbose)
