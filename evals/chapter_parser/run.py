"""Eval runner for the chapter_parser prompt."""
import argparse
import json
import sys
from pathlib import Path

from evals.chapter_parser.in_memory_book_repository import InMemoryBookRepository
from evals.chapter_parser.preloaded_book_source import PreloadedBookSource
from src.ai.ai_provider import AIProvider
from src.ai.claude_code_provider import ClaudeCodeProvider
from src.config import Config
from src.domain.models import Book
from src.prompts.chapter_parser.chapter_parser_prompt_builder import (
    ChapterParserPromptBuilder,
)
from src.trimmers.audibility_trimmer import AudibilityTrimmer
from src.trimmers.beat_trimmer import BeatTrimmer
from src.trimmers.capitalization_trimmer import CapitalizationTrimmer
from src.trimmers.quoted_punctuation_trimmer import QuotedPunctuationTrimmer
from src.trimmers.sentence_ending_trimmer import SentenceEndingTrimmer
from src.validators.assertions_validator import AssertionsValidator
from src.validators.normalizers.lowercase_normalizer import LowercaseNormalizer
from src.validators.normalizers.punctuation_normalizer import PunctuationNormalizer
from src.validators.normalizers.text_normalizer import TextNormalizer
from src.validators.normalizers.whitespace_normalizer import WhitespaceNormalizer
from src.validators.text_validator import TextValidator
from src.validators.validator import Validator
from src.workflows.ai_workflow import AIWorkflow
from src.workflows.workflow import WorkflowRequest

CASES_DIR = Path(__file__).parent

_DEFAULT_BEAT_TRIMMERS: list[BeatTrimmer] = [
    AudibilityTrimmer(),
    QuotedPunctuationTrimmer(),
    SentenceEndingTrimmer(),
    CapitalizationTrimmer(),
]

_DEFAULT_NORMALIZERS: list[TextNormalizer] = [
    PunctuationNormalizer(),
    WhitespaceNormalizer(),
    LowercaseNormalizer(),
]

_DEFAULT_VALIDATORS: list[Validator] = [
    TextValidator(
        _DEFAULT_NORMALIZERS,
        skip_types={
            "book_title_announcement",
            "book_title",
            "chapter_announcement",
        },
    ),
]


def _load_book(path: Path) -> Book:
    return Book.from_dict(json.loads(path.read_text()))


def _save_book(path: Path, book: Book) -> None:
    path.write_text(json.dumps(book.to_dict(), indent=2) + "\n")


def _build_case_validators(case_dir: Path) -> list[Validator]:
    validators: list[Validator] = list(_DEFAULT_VALIDATORS)
    assertions_path = case_dir / "assertions.json"
    if assertions_path.exists():
        validators.append(AssertionsValidator.from_file(assertions_path))
    return validators


def _run_case(case_dir: Path, ai_provider: AIProvider) -> bool:
    print(f"\n=== {case_dir.name} ===", flush=True)
    input_book = _load_book(case_dir / "input.json")

    workflow = AIWorkflow(
        book_source=PreloadedBookSource(input_book),
        prompt_builder=ChapterParserPromptBuilder(),
        ai_provider=ai_provider,
        repository=InMemoryBookRepository(),
        beat_trimmers=_DEFAULT_BEAT_TRIMMERS,
    )

    try:
        output_book = workflow.run(WorkflowRequest(url=case_dir.name))
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        print(f"FAIL: could not parse response ({exc})")
        return False

    _save_book(case_dir / "output.json", output_book)

    validators = _build_case_validators(case_dir)
    results = [
        (type(v).__name__, v.validate(input_book, output_book)) for v in validators
    ]
    for name, result in results:
        print(f"  {name}: deviation={result.deviation:.4f}")

    failures = [name for name, result in results if not result.passed]
    if failures:
        print(f"FAIL: {len(failures)} validator(s) rejected the output")
        for name in failures:
            print(f"  - {name}")
        return False

    print("PASS")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Run chapter_parser eval cases.")
    parser.add_argument(
        "--case", help="run only the case with this id (e.g., 02)",
    )
    args = parser.parse_args()

    case_dirs = sorted(
        d for d in CASES_DIR.iterdir() if d.is_dir() and d.name.isdigit()
    )
    if args.case:
        case_dirs = [d for d in case_dirs if d.name == args.case]
        if not case_dirs:
            print(f"no eval case named {args.case!r} in {CASES_DIR}")
            return 1
    if not case_dirs:
        print(f"no eval cases found in {CASES_DIR}")
        return 1

    ai_provider = ClaudeCodeProvider(Config.from_env())
    results = [_run_case(d, ai_provider) for d in case_dirs]
    passed = sum(results)
    total = len(results)
    print(f"\n=== {passed}/{total} cases passed ===")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
