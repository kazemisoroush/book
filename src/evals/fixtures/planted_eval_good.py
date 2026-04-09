"""Planted good eval scorer with no violations.

This fixture is used by score_eval_auditor.py to test whether the Eval Auditor
correctly identifies clean eval code (precision check).

EXPECTED: No violations should be detected.
"""
from pathlib import Path

from src.evals.eval_harness import EvalHarness

REPO_ROOT = Path(__file__).parent.parent.parent
PLANTED_FILE = REPO_ROOT / "src" / "domain" / "planted_eval_good_test_file.py"
GOLDEN_FILE = Path(__file__).parent / "golden_planted_eval_good.py"


class ScorePlantedEvalGood(EvalHarness):
    """Eval scorer with proper structure (no violations)."""

    def setup(self) -> None:
        """Plant a test file and golden fixture."""
        PLANTED_FILE.write_text("# Planted for eval\n")
        GOLDEN_FILE.write_text("GOLDEN_DATA = ['example1', 'example2']\n")
        print(f"Planted {PLANTED_FILE}")
        print(f"Planted {GOLDEN_FILE}")

    def score(self) -> None:
        """Score with recall and precision checks."""
        recall: list[tuple[str, str, bool]] = []
        precision: list[tuple[str, str, bool]] = []

        # Recall check: Did the agent do what we expected?
        file_removed = not PLANTED_FILE.exists()
        recall.append(("file-removed", "Planted file was removed", file_removed))

        # Precision check: Did the agent avoid false positives?
        golden_intact = GOLDEN_FILE.exists()
        precision.append(("golden-intact", "Golden fixture not deleted", golden_intact))

        # Report results
        self.report(recall, precision)

    def cleanup(self) -> None:
        """Remove all planted files."""
        for path in (PLANTED_FILE, GOLDEN_FILE):
            if path.exists():
                path.unlink()
                print(f"Removed {path}")


if __name__ == "__main__":
    scorer = ScorePlantedEvalGood()
    scorer.main()
