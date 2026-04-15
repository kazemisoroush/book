"""Scorer for the CI/CD Fixer eval.

Plants a module with three deliberate CI failures (lint, type, test),
a companion test file, and a simulated CI log. After the CI/CD Fixer
agent runs, the scorer checks whether all failures were resolved.

Usage:
    # 1. Plant the broken module, tests, and simulated CI log
    python -m src.evals.harness.score_ci_cd_fixer setup

    # 2. Run the CI/CD Fixer agent with a prompt like:
    #    "CI failed on this branch. The log is at /tmp/gh_run_log.txt.
    #     Diagnose and fix all failures. Do not push to remote."

    # 3. Score the results
    python -m src.evals.harness.score_ci_cd_fixer score

    # 4. Clean up
    python -m src.evals.harness.score_ci_cd_fixer cleanup
"""
import re
import shutil
from pathlib import Path

from src.evals.eval_harness import EvalHarness

FIXTURE_DIR = Path(__file__).parent / "fixtures"

# Source fixtures
MODULE_SRC = FIXTURE_DIR / "planted_ci_failures.py"
TEST_SRC = FIXTURE_DIR / "planted_ci_failures_test.py"
LOG_SRC = FIXTURE_DIR / "planted_ci_log.txt"


class ScoreCiCdFixer(EvalHarness):
    """Eval scorer for the CI/CD Fixer agent."""

    def __init__(self) -> None:
        super().__init__()
        # Destinations where the agent will find them
        self.module_dst = self.repo_root / "src" / "domain" / "planted_ci_failures_eval.py"
        self.test_dst = self.repo_root / "src" / "domain" / "planted_ci_failures_eval_test.py"
        self.log_dst = Path("/tmp/gh_run_log.txt")

    def _strip_eval_metadata(self, source: str) -> str:
        """Remove eval-specific markers so the planted file looks like ordinary code."""
        lines = []
        for line in source.split("\n"):
            # Strip BUG: and CLEAN tags
            line = re.sub(r"\s*#\s*BUG:\w+\s*—.*$", "", line)
            line = re.sub(r"\s*#\s*CLEAN\s*—.*$", "", line)
            line = re.sub(r"\s*#\s*CLEAN$", "", line)
            lines.append(line)
        # Replace the module docstring with something neutral
        result = "\n".join(lines)
        result = result.replace(
            "NOT a real module. The eval scorer copies this into src/domain/ as a\n"
            "real .py file at setup time, stripping eval metadata comments.\n"
            "\n"
            "The planted module has three deliberate failures:\n"
            "  1. LINT  — unused import (ruff will flag)\n"
            "  2. TYPE  — wrong return type annotation (mypy will flag)\n"
            "  3. TEST  — logic bug that causes a test failure (pytest will flag)\n"
            "\n"
            "Each line with a bug is tagged:\n"
            "  # BUG:LINT  — ruff failure\n"
            "  # BUG:TYPE  — mypy failure\n"
            "  # BUG:TEST  — pytest failure\n"
            "  # CLEAN     — must not be changed",
            "Helpers for text processing and simple math.",
        )
        return result

    def setup(self) -> None:
        """Plant the broken module, test file, and CI log."""
        # Plant the module (with eval metadata stripped)
        source = MODULE_SRC.read_text()
        cleaned = self._strip_eval_metadata(source)
        self.module_dst.write_text(cleaned)
        print(f"  planted  {self.module_dst.relative_to(self.repo_root)}")

        # Plant the test file (no metadata to strip)
        shutil.copy2(TEST_SRC, self.test_dst)
        print(f"  planted  {self.test_dst.relative_to(self.repo_root)}")

        # Plant the CI log
        shutil.copy2(LOG_SRC, self.log_dst)
        print(f"  planted  {self.log_dst}")

        # Verify the failures exist
        print("\nVerifying planted failures:")

        r = self._run_cmd(["ruff", "check", str(self.module_dst)])
        lint_fails = r.returncode != 0
        print(f"  ruff:   {'FAILS as expected' if lint_fails else 'ERROR — should fail'}")

        r = self._run_cmd(["mypy", str(self.module_dst)])
        type_fails = r.returncode != 0
        print(f"  mypy:   {'FAILS as expected' if type_fails else 'ERROR — should fail'}")

        r = self._run_cmd(["pytest", "-x", str(self.test_dst), "--no-header", "-q"])
        test_fails = r.returncode != 0
        print(f"  pytest: {'FAILS as expected' if test_fails else 'ERROR — should fail'}")

        print()
        print("Setup complete. Now run the CI/CD Fixer agent with a prompt like:")
        print('  "CI failed on this branch. The log is at /tmp/gh_run_log.txt.')
        print('   Diagnose and fix all failures locally. Do not push to remote."')
        print()
        print("Then: python -m src.evals.harness.score_ci_cd_fixer score")

    def score(self) -> None:
        """Check if the CI/CD Fixer resolved all three failure categories."""
        if not self.module_dst.exists():
            print("ERROR: planted module was deleted. Agent should fix, not delete.")
            return

        if not self.test_dst.exists():
            print("ERROR: test file was deleted. Agent should NOT touch tests.")
            return

        test_content = self.test_dst.read_text()

        # Recall checks (failures the agent MUST fix)

        # 1. Lint: unused import removed
        r = self._run_cmd(["ruff", "check", str(self.module_dst)])
        lint_fixed = r.returncode == 0
        lint_detail = r.stdout.strip() if not lint_fixed else "clean"

        # 2. Type: return type matches annotation
        r = self._run_cmd(["mypy", str(self.module_dst)])
        type_fixed = r.returncode == 0
        type_detail = r.stdout.strip() if not type_fixed else "clean"

        # 3. Test: all tests pass
        r = self._run_cmd(["pytest", "-x", str(self.test_dst), "--no-header", "-q"])
        test_fixed = r.returncode == 0
        test_detail = r.stdout.strip() if not test_fixed else "all pass"

        # Precision checks (things the agent must NOT break)

        # 4. Test file unchanged — agent must fix impl, not tests
        original_test = TEST_SRC.read_text()
        test_preserved = test_content == original_test

        # 5. strip_markup function still works (wasn't broken, shouldn't be touched)
        r = self._run_cmd([
            "python", "-c",
            "from src.domain.planted_ci_failures_eval import strip_markup; "
            "assert strip_markup('<b>hi</b>') == 'hi'",
        ])
        clean_code_preserved = r.returncode == 0

        # 6. Full check suite still passes (no collateral damage)
        # Exclude other eval fixtures that import modules only present during their own setup.
        r = self._run_cmd([
            "pytest", "--no-header", "-q",
            "--ignore=src/evals/harness/fixtures",
        ])
        full_suite_passes = r.returncode == 0

        # 7. word_count returns int (not just "passes" — the fix must be correct)
        r = self._run_cmd([
            "python", "-c",
            "from src.domain.planted_ci_failures_eval import word_count; "
            "r = word_count('a b c'); assert r == 3 and isinstance(r, int)",
        ])
        word_count_correct = r.returncode == 0

        # 8. double_value returns correct result
        r = self._run_cmd([
            "python", "-c",
            "from src.domain.planted_ci_failures_eval import double_value; "
            "assert double_value(7) == 14 and double_value(0) == 0",
        ])
        double_value_correct = r.returncode == 0

        # Build check lists
        recall_checks = [
            ("lint-fixed",          "Unused import removed (ruff passes)",     lint_fixed),
            ("type-fixed",          "Return type corrected (mypy passes)",     type_fixed),
            ("test-fixed",          "Logic bugs fixed (pytest passes)",        test_fixed),
            ("word-count-correct",  "word_count returns int 3 for 'a b c'",   word_count_correct),
            ("double-value-correct", "double_value(7) == 14",                 double_value_correct),
        ]

        precision_checks = [
            ("test-preserved",       "Test file not modified",                 test_preserved),
            ("clean-code-preserved", "strip_markup still works correctly",     clean_code_preserved),
            ("full-suite-passes",    "Full pytest suite still passes",         full_suite_passes),
        ]

        # Print report
        print("=" * 55)
        print("CI/CD FIXER EVAL RESULTS")
        print("=" * 55)

        # Print detailed info for failures
        for tag, desc, ok in recall_checks:
            if not ok:
                if tag == "lint-fixed":
                    print(f"  LINT DETAIL: {lint_detail}")
                elif tag == "type-fixed":
                    print(f"  TYPE DETAIL: {type_detail}")
                elif tag == "test-fixed":
                    print(f"  TEST DETAIL: {test_detail}")

        self.report(recall_checks, precision_checks)

    def cleanup(self) -> None:
        """Remove planted files."""
        for path in (self.module_dst, self.test_dst, self.log_dst):
            if path.exists():
                path.unlink()
                print(f"Removed {path}")
        print("Clean.")


if __name__ == "__main__":
    ScoreCiCdFixer().main()
