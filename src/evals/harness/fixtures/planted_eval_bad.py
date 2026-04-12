"""Planted bad eval scorer with intentional violations.

This fixture is used by score_eval_auditor.py to test whether the Eval Auditor
detects eval quality violations.

VIOLATIONS PLANTED:
- MISSING_RECALL: No recall checks (no recall.append or recall list)
- MISSING_PRECISION: No precision checks (no precision.append or precision list)
- MISSING_CLEANUP: cleanup() does not remove planted files
- NO_HARNESS: Does not subclass EvalHarness
- BAD_NAMING: Golden fixture has wrong name (golden_planted_eval_wrong_name.py)
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
PLANTED_FILE = REPO_ROOT / "src" / "domain" / "planted_eval_test_file.py"
GOLDEN_FILE = Path(__file__).parent / "golden_planted_eval_wrong_name.py"  # VIOLATION: bad naming


def setup() -> None:
    """Plant a test file."""
    PLANTED_FILE.write_text("# Planted for eval\n")
    GOLDEN_FILE.write_text("GOLDEN_DATA = []\n")
    print(f"Planted {PLANTED_FILE}")


def score() -> None:
    """Score the results (no recall or precision checks)."""
    # VIOLATION: No recall or precision checks
    print("Checking results...")
    if PLANTED_FILE.exists():
        print("  File still exists")
    else:
        print("  File was removed")
    # No self.report() call, no recall/precision lists
    print("Score: PASS")


def cleanup() -> None:
    """Clean up (incomplete - doesn't remove planted files)."""
    # VIOLATION: Does not remove planted files
    print("Cleanup complete")  # Lies! Files still exist


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd == "setup":
        setup()
    elif cmd == "score":
        score()
    elif cmd == "cleanup":
        cleanup()
    else:
        print("Usage: python -m src.evals.harness.fixtures.planted_eval_bad [setup|score|cleanup]")
