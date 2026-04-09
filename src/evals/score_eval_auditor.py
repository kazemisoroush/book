"""Scorer for the Eval Auditor eval.

Plants two eval scorers with different quality levels and checks whether the
Eval Auditor correctly identifies violations in the bad eval and doesn't flag
the good eval.

Usage:
    python -m src.evals.score_eval_auditor setup
    # run the Eval Auditor agent
    python -m src.evals.score_eval_auditor score
    python -m src.evals.score_eval_auditor cleanup
"""
import ast
import sys
from pathlib import Path

from src.evals.eval_harness import EvalHarness

FIXTURE_DIR = Path(__file__).parent / "fixtures"
BAD_EVAL_SRC = FIXTURE_DIR / "planted_eval_bad.py"
GOOD_EVAL_SRC = FIXTURE_DIR / "planted_eval_good.py"
BAD_EVAL_DST = Path(__file__).parent / "score_planted_eval_bad.py"
GOOD_EVAL_DST = Path(__file__).parent / "score_planted_eval_good.py"


class ScoreEvalAuditor(EvalHarness):
    """Eval scorer for the Eval Auditor agent."""

    def setup(self) -> None:
        """Copy planted eval fixtures into src/evals/ where the auditor will find them."""
        import shutil
        shutil.copy2(BAD_EVAL_SRC, BAD_EVAL_DST)
        shutil.copy2(GOOD_EVAL_SRC, GOOD_EVAL_DST)
        print(f"Planted bad eval at {BAD_EVAL_DST}")
        print(f"Planted good eval at {GOOD_EVAL_DST}")
        print()
        print("Now run the Eval Auditor agent, then:")
        print("  python -m src.evals.score_eval_auditor score")

    def score(self) -> None:
        """Check if the Eval Auditor fixed issues in the bad eval and preserved the good eval."""
        if not BAD_EVAL_DST.exists() or not GOOD_EVAL_DST.exists():
            print("ERROR: Planted eval files were deleted. The auditor should edit, not delete.")
            sys.exit(1)

        # Read the planted files to check what the auditor changed
        bad_content = BAD_EVAL_DST.read_text()
        good_content = GOOD_EVAL_DST.read_text()

        recall: list[tuple[str, str, bool]] = []
        precision: list[tuple[str, str, bool]] = []

        # ── Recall 1: Bad eval - fixed missing cleanup ──────────────────────
        # The auditor should FIX the cleanup() method to remove planted files
        try:
            tree = ast.parse(bad_content)
            cleanup_func = None
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == "cleanup":
                    cleanup_func = ast.get_source_segment(bad_content, node)
                    break

            if cleanup_func:
                # Check if it removes PLANTED_FILE or GOLDEN_FILE
                removes_planted = "PLANTED_FILE" in cleanup_func and "unlink" in cleanup_func
                removes_golden = "GOLDEN_FILE" in cleanup_func and "unlink" in cleanup_func
                cleanup_fixed = removes_planted and removes_golden
            else:
                cleanup_fixed = False
        except Exception:
            cleanup_fixed = False

        recall.append((
            "cleanup-fixed",
            "Fixed incomplete cleanup() to remove planted files",
            cleanup_fixed,
        ))

        # ── Precision 1: Good eval - preserved EvalHarness ──────────────────
        good_has_harness = "EvalHarness" in good_content and "class" in good_content
        precision.append((
            "good-harness-preserved",
            "Good eval still subclasses EvalHarness",
            good_has_harness,
        ))

        # ── Precision 2: Good eval - preserved recall checks ────────────────
        good_has_recall = "recall" in good_content and "recall.append" in good_content
        precision.append((
            "good-recall-preserved",
            "Good eval still has recall checks",
            good_has_recall,
        ))

        # ── Precision 3: Good eval - preserved precision checks ─────────────
        good_has_precision = "precision" in good_content and "precision.append" in good_content
        precision.append((
            "good-precision-preserved",
            "Good eval still has precision checks",
            good_has_precision,
        ))

        # ── Precision 4: Good eval - preserved cleanup ──────────────────────
        try:
            tree = ast.parse(good_content)
            good_cleanup_func = None
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == "cleanup":
                    good_cleanup_func = ast.get_source_segment(good_content, node)
                    break
            good_cleanup_intact = good_cleanup_func is not None and "unlink" in good_cleanup_func
        except Exception:
            good_cleanup_intact = False

        precision.append((
            "good-cleanup-preserved",
            "Good eval cleanup() still intact",
            good_cleanup_intact,
        ))

        # Report results
        self.report(recall, precision)

    def cleanup(self) -> None:
        """Remove planted eval files."""
        for path in (BAD_EVAL_DST, GOOD_EVAL_DST):
            if path.exists():
                path.unlink()
                print(f"Removed {path}")

        # Also clean up any files the planted evals might have created
        domain_dir = self.repo_root / "src" / "domain"
        for pattern in ("planted_eval_test_file.py", "planted_eval_good_test_file.py"):
            for path in domain_dir.glob(pattern):
                path.unlink()
                print(f"Removed {path}")

        # Clean up any golden fixtures created
        golden_dir = FIXTURE_DIR
        for pattern in ("golden_planted_eval_wrong_name.py", "golden_planted_eval_good.py"):
            for path in golden_dir.glob(pattern):
                path.unlink()
                print(f"Removed {path}")


if __name__ == "__main__":
    scorer = ScoreEvalAuditor()
    scorer.main()
