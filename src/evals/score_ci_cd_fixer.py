"""Scorer for the CI/CD Fixer eval.

Plants a module with three deliberate CI failures (lint, type, test),
a companion test file, and a simulated CI log. After the CI/CD Fixer
agent runs, the scorer checks whether all failures were resolved.

Usage:
    # 1. Plant the broken module, tests, and simulated CI log
    python -m src.evals.score_ci_cd_fixer setup

    # 2. Run the CI/CD Fixer agent with a prompt like:
    #    "CI failed on this branch. The log is at /tmp/gh_run_log.txt.
    #     Diagnose and fix all failures. Do not push to remote."

    # 3. Score the results
    python -m src.evals.score_ci_cd_fixer score

    # 4. Clean up
    python -m src.evals.score_ci_cd_fixer cleanup
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

FIXTURE_DIR = Path(__file__).parent / "fixtures"
REPO_ROOT = Path(__file__).parent.parent.parent

# Source fixtures
MODULE_SRC = FIXTURE_DIR / "planted_ci_failures.py"
TEST_SRC = FIXTURE_DIR / "planted_ci_failures_test.py"
LOG_SRC = FIXTURE_DIR / "planted_ci_log.txt"

# Destinations where the agent will find them
MODULE_DST = REPO_ROOT / "src" / "domain" / "planted_ci_failures_eval.py"
TEST_DST = REPO_ROOT / "src" / "domain" / "planted_ci_failures_eval_test.py"
LOG_DST = Path("/tmp/gh_run_log.txt")


def _strip_eval_metadata(source: str) -> str:
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


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Run a command and return the result."""
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=cwd or REPO_ROOT,
    )


def setup() -> None:
    """Plant the broken module, test file, and CI log."""
    # Plant the module (with eval metadata stripped)
    source = MODULE_SRC.read_text()
    cleaned = _strip_eval_metadata(source)
    MODULE_DST.write_text(cleaned)
    print(f"  planted  {MODULE_DST.relative_to(REPO_ROOT)}")

    # Plant the test file (no metadata to strip)
    shutil.copy2(TEST_SRC, TEST_DST)
    print(f"  planted  {TEST_DST.relative_to(REPO_ROOT)}")

    # Plant the CI log
    shutil.copy2(LOG_SRC, LOG_DST)
    print(f"  planted  {LOG_DST}")

    # Verify the failures exist
    print("\nVerifying planted failures:")

    r = _run(["ruff", "check", str(MODULE_DST)])
    lint_fails = r.returncode != 0
    print(f"  ruff:   {'FAILS as expected' if lint_fails else 'ERROR — should fail'}")

    r = _run(["mypy", str(MODULE_DST)])
    type_fails = r.returncode != 0
    print(f"  mypy:   {'FAILS as expected' if type_fails else 'ERROR — should fail'}")

    r = _run(["pytest", "-x", str(TEST_DST), "--no-header", "-q"])
    test_fails = r.returncode != 0
    print(f"  pytest: {'FAILS as expected' if test_fails else 'ERROR — should fail'}")

    print()
    print("Setup complete. Now run the CI/CD Fixer agent with a prompt like:")
    print('  "CI failed on this branch. The log is at /tmp/gh_run_log.txt.')
    print('   Diagnose and fix all failures locally. Do not push to remote."')
    print()
    print("Then: python -m src.evals.score_ci_cd_fixer score")


def score() -> None:
    """Check if the CI/CD Fixer resolved all three failure categories."""
    if not MODULE_DST.exists():
        print("ERROR: planted module was deleted. Agent should fix, not delete.")
        return

    if not TEST_DST.exists():
        print("ERROR: test file was deleted. Agent should NOT touch tests.")
        return

    test_content = TEST_DST.read_text()

    # ── Recall checks (failures the agent MUST fix) ───────────────────

    # 1. Lint: unused import removed
    r = _run(["ruff", "check", str(MODULE_DST)])
    lint_fixed = r.returncode == 0
    lint_detail = r.stdout.strip() if not lint_fixed else "clean"

    # 2. Type: return type matches annotation
    r = _run(["mypy", str(MODULE_DST)])
    type_fixed = r.returncode == 0
    type_detail = r.stdout.strip() if not type_fixed else "clean"

    # 3. Test: all tests pass
    r = _run(["pytest", "-x", str(TEST_DST), "--no-header", "-q"])
    test_fixed = r.returncode == 0
    test_detail = r.stdout.strip() if not test_fixed else "all pass"

    # ── Precision checks (things the agent must NOT break) ────────────

    # 4. Test file unchanged — agent must fix impl, not tests
    original_test = TEST_SRC.read_text()
    test_preserved = test_content == original_test

    # 5. strip_markup function still works (wasn't broken, shouldn't be touched)
    r = _run([
        "python", "-c",
        "from src.domain.planted_ci_failures_eval import strip_markup; "
        "assert strip_markup('<b>hi</b>') == 'hi'",
    ])
    clean_code_preserved = r.returncode == 0

    # 6. Full check suite still passes (no collateral damage)
    #    Exclude other eval fixtures that import modules only present during their own setup.
    r = _run([
        "pytest", "--no-header", "-q",
        "--ignore=src/evals/fixtures",
    ])
    full_suite_passes = r.returncode == 0

    # 7. word_count returns int (not just "passes" — the fix must be correct)
    r = _run([
        "python", "-c",
        "from src.domain.planted_ci_failures_eval import word_count; "
        "r = word_count('a b c'); assert r == 3 and isinstance(r, int)",
    ])
    word_count_correct = r.returncode == 0

    # 8. double_value returns correct result
    r = _run([
        "python", "-c",
        "from src.domain.planted_ci_failures_eval import double_value; "
        "assert double_value(7) == 14 and double_value(0) == 0",
    ])
    double_value_correct = r.returncode == 0

    # ── Report ────────────────────────────────────────────────────────
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

    print("=" * 55)
    print("CI/CD FIXER EVAL RESULTS")
    print("=" * 55)

    total_recall = len(recall_checks)
    passed_recall = sum(1 for _, _, ok in recall_checks if ok)

    print(f"\nFailure resolution (recall): {passed_recall}/{total_recall}")
    for tag, desc, ok in recall_checks:
        status = "PASS" if ok else "FAIL"
        print(f"  {status}  {tag}: {desc}")
        if not ok and tag == "lint-fixed":
            print(f"         {lint_detail}")
        if not ok and tag == "type-fixed":
            print(f"         {type_detail}")
        if not ok and tag == "test-fixed":
            print(f"         {test_detail}")

    total_precision = len(precision_checks)
    passed_precision = sum(1 for _, _, ok in precision_checks if ok)

    print(f"\nCollateral damage (precision): {passed_precision}/{total_precision}")
    for tag, desc, ok in precision_checks:
        status = "PASS" if ok else "FAIL"
        print(f"  {status}  {tag}: {desc}")

    recall = passed_recall / total_recall if total_recall else 0
    precision = passed_precision / total_precision if total_precision else 0
    print(f"\nRecall:    {recall:.0%} ({passed_recall}/{total_recall} failures resolved)")
    print(f"Precision: {precision:.0%} ({passed_precision}/{total_precision} clean code preserved)")
    print(f"Score:     {'PASS' if recall == 1.0 and precision == 1.0 else 'FAIL'}")


def cleanup() -> None:
    """Remove planted files."""
    for path in (MODULE_DST, TEST_DST, LOG_DST):
        if path.exists():
            path.unlink()
            print(f"Removed {path}")
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
        print("Usage: python -m src.evals.score_ci_cd_fixer [setup|score|cleanup]")
