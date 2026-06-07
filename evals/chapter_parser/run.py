"""Eval runner for the chapter_parser prompt."""
import json
import sys
from dataclasses import asdict
from pathlib import Path

from src.ai.ai_provider import AIProvider
from src.ai.claude_code_provider import ClaudeCodeProvider
from src.config import Config
from src.prompts.chapter_parser.chapter_parser_prompt_builder import (
    ChapterParserPromptBuilder,
)
from src.prompts.chapter_parser.input import (
    PromptInput,
    PromptInputChapter,
    PromptInputCharacter,
    PromptInputMetadata,
    PromptInputSection,
)
from src.prompts.chapter_parser.output import PromptOutput
from src.trimmers.audibility_trimmer import AudibilityTrimmer
from src.trimmers.beat_trimmer import BeatTrimmer
from src.trimmers.beat_trimmer_pipeline import apply_beat_trimmers
from src.trimmers.capitalization_trimmer import CapitalizationTrimmer
from src.trimmers.quoted_punctuation_trimmer import QuotedPunctuationTrimmer
from src.trimmers.sentence_ending_trimmer import SentenceEndingTrimmer
from src.validators.normalizers.lowercase_normalizer import LowercaseNormalizer
from src.validators.normalizers.punctuation_normalizer import PunctuationNormalizer
from src.validators.normalizers.text_normalizer import TextNormalizer
from src.validators.normalizers.whitespace_normalizer import WhitespaceNormalizer
from src.validators.text_validator import TextValidator
from src.validators.validator import Validator

CASES_DIR = Path(__file__).parent
MAX_TOKENS = 16000

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
        skip_types={"book_title_announcement", "chapter_announcement"},
    ),
]


def _load_input(path: Path) -> PromptInput:
    data = json.loads(path.read_text())
    return PromptInput(
        metadata=PromptInputMetadata(**data["metadata"]),
        chapters=[
            PromptInputChapter(
                id=ch["id"],
                sections=[PromptInputSection(**s) for s in ch["sections"]],
            )
            for ch in data["chapters"]
        ],
        characters=[
            PromptInputCharacter(**c) for c in data.get("characters", [])
        ],
    )


def _save_output(path: Path, output: PromptOutput) -> None:
    path.write_text(json.dumps(asdict(output), indent=2) + "\n")


def _run_case(
    case_dir: Path, provider: AIProvider, validators: list[Validator],
) -> bool:
    print(f"\n=== {case_dir.name} ===", flush=True)
    prompt_input = _load_input(case_dir / "input.json")

    prompt = ChapterParserPromptBuilder().with_chapter(prompt_input).build()
    raw = provider.generate(prompt, max_tokens=MAX_TOKENS)

    try:
        actual = PromptOutput.from_dict(json.loads(raw))
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        print(f"FAIL: could not parse response ({exc})")
        print(f"  raw response (first 500 chars): {raw[:500]!r}")
        return False

    actual = apply_beat_trimmers(actual, _DEFAULT_BEAT_TRIMMERS)
    _save_output(case_dir / "output.json", actual)

    results = [(type(v).__name__, v.validate(prompt_input, actual)) for v in validators]
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
    case_dirs = sorted(
        d for d in CASES_DIR.iterdir() if d.is_dir() and d.name.isdigit()
    )
    if not case_dirs:
        print(f"no eval cases found in {CASES_DIR}")
        return 1

    provider = ClaudeCodeProvider(Config.from_env())
    results = [_run_case(d, provider, _DEFAULT_VALIDATORS) for d in case_dirs]
    passed = sum(results)
    total = len(results)
    print(f"\n=== {passed}/{total} cases passed ===")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
