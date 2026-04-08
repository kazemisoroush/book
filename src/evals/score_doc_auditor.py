"""Scorer for the Doc Auditor eval.

Usage:
    python -m src.evals.score_doc_auditor setup
    # run the Doc Auditor agent
    python -m src.evals.score_doc_auditor score
    python -m src.evals.score_doc_auditor cleanup
"""
import re
import shutil
import sys
from pathlib import Path

FIXTURE_DIR = Path(__file__).parent / "fixtures"
MODULE_SRC = FIXTURE_DIR / "planted_doc_drift.py"
TEST_SRC = FIXTURE_DIR / "planted_doc_drift_test.py"
MODULE_DST = Path(__file__).parent.parent / "domain" / "planted_doc_drift_eval.py"
TEST_DST = Path(__file__).parent.parent / "domain" / "planted_doc_drift_eval_test.py"

# The drifted module docstring (what gets planted)
DRIFTED_DOCSTRING = '''\
"""Helpers for text chunk processing.

Public API:

- ``split_text(text)`` — split text into sentences
- ``count_words(text) -> int`` — count words in text
- ``merge_chunks(chunks, separator) -> str`` — merge chunks with separator
- ``normalize_case(text) -> str`` — normalize text to lowercase
"""'''

# Drift expectations: (category, check_description, checker_function)
# Each checker takes the module docstring after the auditor runs and returns True if fixed.


def _check_stale_name(docstring: str) -> bool:
    """split_text should be replaced with split_into_sentences."""
    return "split_text" not in docstring and "split_into_sentences" in docstring


def _check_correct_entry(docstring: str) -> bool:
    """count_words should still be present (was correct)."""
    return "count_words" in docstring


def _check_stale_signature(docstring: str) -> bool:
    """merge_chunks signature should not list separator as a parameter."""
    has_merge = "merge_chunks" in docstring
    # Check the signature portion only — (chunks, separator) should become (chunks)
    # The word "separator" in a description is fine; only flag it in the signature
    no_separator_param = "merge_chunks(chunks, separator)" not in docstring
    return has_merge and no_separator_param


def _check_removed_entry(docstring: str) -> bool:
    """normalize_case should be removed (function doesn't exist)."""
    return "normalize_case" not in docstring


def _check_missing_entry(docstring: str) -> bool:
    """deduplicate_chunks should be added (public function not listed)."""
    return "deduplicate_chunks" in docstring


DRIFT_CHECKS = [
    ("stale-name",       "split_text → split_into_sentences",    _check_stale_name,       True),
    ("correct-entry",    "count_words preserved",                 _check_correct_entry,    False),
    ("stale-signature",  "merge_chunks(separator) → merge_chunks(chunks)", _check_stale_signature, True),
    ("removed-entry",    "normalize_case removed",                _check_removed_entry,    True),
    ("missing-entry",    "deduplicate_chunks added",              _check_missing_entry,    True),
]


def setup() -> None:
    """Plant a module with drifted docstring into domain/."""
    source = MODULE_SRC.read_text()

    # Extract just the code (functions), skip the fixture metadata
    # Build the planted file: drifted docstring + actual functions
    code_lines = []
    in_code = False
    for line in source.split("\n"):
        if line.startswith("def ") or in_code:
            in_code = True
            # Strip eval tags
            line = re.sub(r'\s*#\s*DRIFT:\S+.*$', '', line)
            line = re.sub(r'\s*#\s*CORRECT.*$', '', line)
            code_lines.append(line)

    planted = DRIFTED_DOCSTRING + "\n\n\n" + "\n".join(code_lines) + "\n"
    MODULE_DST.write_text(planted)
    shutil.copy2(TEST_SRC, TEST_DST)
    print(f"Planted module at {MODULE_DST}")
    print(f"Planted tests  at {TEST_DST}")
    print("Now run the Doc Auditor agent, then: python -m src.evals.score_doc_auditor score")


def score() -> None:
    """Check if the Doc Auditor fixed the drifted docstring."""
    if not MODULE_DST.exists():
        print("ERROR: planted module was deleted. Agent should edit, not delete.")
        return

    content = MODULE_DST.read_text()

    # Extract the module docstring
    match = re.match(r'"""(.*?)"""', content, re.DOTALL)
    if not match:
        # Try single-quote docstring
        match = re.match(r"'''(.*?)'''", content, re.DOTALL)
    docstring = match.group(0) if match else content

    fixed_drift = []
    missed_drift = []
    preserved = []
    damaged = []

    for category, description, checker, is_drift in DRIFT_CHECKS:
        passed = checker(docstring)
        if is_drift:
            if passed:
                fixed_drift.append((category, description))
            else:
                missed_drift.append((category, description))
        else:
            if passed:
                preserved.append((category, description))
            else:
                damaged.append((category, description))

    total_drift = sum(1 for _, _, _, d in DRIFT_CHECKS if d)
    total_correct = sum(1 for _, _, _, d in DRIFT_CHECKS if not d)

    print("=" * 50)
    print("DOC AUDITOR EVAL RESULTS")
    print("=" * 50)

    print(f"\nDrift detection (recall): {len(fixed_drift)}/{total_drift}")
    for cat, desc in sorted(fixed_drift):
        print(f"  PASS  {cat}: {desc}")
    for cat, desc in sorted(missed_drift):
        print(f"  FAIL  {cat}: {desc}")

    print(f"\nCorrect doc preservation (precision): {len(preserved)}/{total_correct}")
    for cat, desc in sorted(preserved):
        print(f"  PASS  {cat}: {desc}")
    for cat, desc in sorted(damaged):
        print(f"  FAIL  {cat}: {desc}")

    recall = len(fixed_drift) / total_drift if total_drift else 0
    precision = len(preserved) / total_correct if total_correct else 0
    print(f"\nRecall:    {recall:.0%} ({len(fixed_drift)}/{total_drift} drifts fixed)")
    print(f"Precision: {precision:.0%} ({len(preserved)}/{total_correct} correct entries kept)")
    print(f"Score:     {'PASS' if recall == 1.0 and precision == 1.0 else 'FAIL'}")


def cleanup() -> None:
    """Remove planted files from domain/."""
    for path in (MODULE_DST, TEST_DST):
        if path.exists():
            path.unlink()
            print(f"Removed {path}")
    if not MODULE_DST.exists() and not TEST_DST.exists():
        print("Clean.")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd == "setup":
        setup()
    elif cmd == "score":
        score()
    elif cmd == "cleanup":
        cleanup()
    else:
        print("Usage: python -m src.evals.score_doc_auditor [setup|score|cleanup]")
