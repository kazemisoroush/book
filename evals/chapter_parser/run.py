"""Eval runner for the chapter_parser prompt."""
import json
import sys
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

CASES_DIR = Path(__file__).parent
MAX_TOKENS = 16000

_DEFAULT_BEAT_TRIMMERS: list[BeatTrimmer] = [
    AudibilityTrimmer(),
    QuotedPunctuationTrimmer(),
    SentenceEndingTrimmer(),
    CapitalizationTrimmer(),
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


def _load_expected(path: Path) -> PromptOutput:
    return PromptOutput.from_dict(json.loads(path.read_text()))


def _diff(expected: PromptOutput, actual: PromptOutput) -> list[str]:
    failures: list[str] = []
    actual_chapters = {ch.id: ch for ch in actual.chapters}
    for exp_ch in expected.chapters:
        act_ch = actual_chapters.get(exp_ch.id)
        if act_ch is None:
            failures.append(f"chapter {exp_ch.id} missing in response")
            continue
        actual_beats = {b.id: b for b in act_ch.beats}
        for exp_b in exp_ch.beats:
            act_b = actual_beats.get(exp_b.id)
            if act_b is None:
                failures.append(
                    f"ch{exp_ch.id} beat#{exp_b.id} missing in response"
                )
                continue
            if act_b.text != exp_b.text:
                failures.append(
                    f"ch{exp_ch.id} beat#{exp_b.id} text mismatch\n"
                    f"    expected: {exp_b.text!r}\n"
                    f"    actual:   {act_b.text!r}"
                )
            if act_b.character_id != exp_b.character_id:
                failures.append(
                    f"ch{exp_ch.id} beat#{exp_b.id} character_id mismatch "
                    f"(expected {exp_b.character_id}, actual {act_b.character_id})"
                )
    return failures


def _run_case(case_dir: Path, provider: AIProvider) -> bool:
    print(f"\n=== {case_dir.name} ===", flush=True)
    prompt_input = _load_input(case_dir / "input.json")
    expected = _load_expected(case_dir / "output.json")

    prompt = ChapterParserPromptBuilder().with_chapter(prompt_input).build()
    raw = provider.generate(prompt, max_tokens=MAX_TOKENS)

    try:
        actual = PromptOutput.from_dict(json.loads(raw))
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        print(f"FAIL: could not parse response ({exc})")
        print(f"  raw response (first 500 chars): {raw[:500]!r}")
        return False

    actual = apply_beat_trimmers(actual, _DEFAULT_BEAT_TRIMMERS)

    failures = _diff(expected, actual)
    if failures:
        print(f"FAIL: {len(failures)} assertion(s)")
        for f in failures:
            print(f"  - {f}")
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
    results = [_run_case(d, provider) for d in case_dirs]
    passed = sum(results)
    total = len(results)
    print(f"\n=== {passed}/{total} cases passed ===")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
