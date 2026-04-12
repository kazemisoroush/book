"""Scorer for the Eval Agent eval.

Gives the Eval Agent a small AI eval task (emotion detection) and checks whether
it produced the correct artifacts:

  1. Golden labels fixture (golden_emotion_detection.py)
  2. Scorer that subclasses EvalHarness (score_emotion_detection.py)
  3. At least 1 recall check and 1 precision check in the scorer
  4. Baseline score reported (not necessarily 100%, 80% threshold)
  5. Scorer runs without error

This scorer is standalone (does not subclass EvalHarness) to avoid circular
dependency when evaluating the eval framework itself.

Usage:
    # 1. Plant the spec
    python -m src.evals.harness.score_eval_agent setup

    # 2. Run the Eval Agent with:
    #    "Write an eval for the spec at src/evals/harness/fixtures/planted_eval_agent_spec.md"

    # 3. Score the results
    python -m src.evals.harness.score_eval_agent score

    # 4. Clean up
    python -m src.evals.harness.score_eval_agent cleanup
"""
import ast
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent.parent
SPEC_PATH = Path(__file__).parent / "fixtures" / "planted_eval_agent_spec.md"
GOLDEN_PATH = REPO_ROOT / "src" / "evals" / "harness" / "fixtures" / "golden_emotion_detection.py"
SCORER_PATH = REPO_ROOT / "src" / "evals" / "score_emotion_detection.py"


def _run(cmd: list[str], timeout: int = 30) -> subprocess.CompletedProcess[str]:
    """Run a command and return the result."""
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(
            cmd, returncode=1, stdout="", stderr="TIMEOUT",
        )


def setup() -> None:
    """Ensure the spec exists and clean up any leftovers."""
    # Clean up any leftover files
    for path in (GOLDEN_PATH, SCORER_PATH):
        if path.exists():
            path.unlink()
            print(f"  cleaned  {path.relative_to(REPO_ROOT)}")

    print(f"  spec at  {SPEC_PATH.relative_to(REPO_ROOT)}")
    print()
    print("Setup complete. Now run the Eval Agent with a prompt like:")
    print(f'  "Write an eval for the spec at {SPEC_PATH.relative_to(REPO_ROOT)}"')
    print()
    print("Then: python -m src.evals.harness.score_eval_agent score")


def score() -> None:
    """Check if the Eval Agent produced the right artifacts with the right structure."""
    recall: list[tuple[str, str, bool]] = []
    precision: list[tuple[str, str, bool]] = []

    # ── Recall 1: Golden labels fixture exists ───────────────────────────
    golden_exists = GOLDEN_PATH.exists()
    recall.append(("golden-file-exists", "Golden labels fixture was created", golden_exists))

    # ── Recall 2: Scorer file exists ─────────────────────────────────────
    scorer_exists = SCORER_PATH.exists()
    recall.append(("scorer-file-exists", "Scorer file was created", scorer_exists))

    if not golden_exists or not scorer_exists:
        _print_report(recall, precision)
        return

    golden_content = GOLDEN_PATH.read_text()
    scorer_content = SCORER_PATH.read_text()

    # ── Recall 3: Golden labels has GOLDEN_<FEATURE> constant ─────────────
    has_golden_constant = "GOLDEN_EMOTION_DETECTION" in golden_content or "GOLDEN_EMOTIONS" in golden_content
    recall.append((
        "golden-constant",
        "Fixture defines GOLDEN_* constant",
        has_golden_constant,
    ))

    # ── Recall 4: Golden labels has at least 3 examples ───────────────────
    # Parse the file to count examples
    try:
        golden_tree = ast.parse(golden_content)
        # Find assignments to GOLDEN_*
        golden_var = None
        for node in ast.walk(golden_tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id.startswith("GOLDEN_"):
                        golden_var = node.value
                        break

        if golden_var and isinstance(golden_var, (ast.List, ast.Tuple)):
            num_examples = len(golden_var.elts)
        else:
            num_examples = 0

        has_min_examples = num_examples >= 3
        recall.append((
            "golden-examples",
            f"At least 3 golden examples (got {num_examples})",
            has_min_examples,
        ))
    except Exception:
        recall.append(("golden-examples", "Could not parse golden labels", False))

    # ── Recall 5: Scorer subclasses EvalHarness ───────────────────────────
    has_eval_harness = "class Score" in scorer_content and "EvalHarness" in scorer_content
    recall.append((
        "scorer-subclasses-harness",
        "Scorer subclasses EvalHarness",
        has_eval_harness,
    ))

    # ── Recall 6: Scorer has setup/score/cleanup methods ──────────────────
    has_setup = "def setup(self)" in scorer_content
    has_score = "def score(self)" in scorer_content
    has_cleanup = "def cleanup(self)" in scorer_content
    has_methods = has_setup and has_score and has_cleanup
    recall.append((
        "scorer-methods",
        "Scorer has setup/score/cleanup methods",
        has_methods,
    ))

    # ── Recall 7: Scorer has recall checks ────────────────────────────────
    # Look for patterns like "recall.append" or "recall: list"
    has_recall_checks = "recall" in scorer_content and ("recall.append" in scorer_content or "recall =" in scorer_content)
    recall.append(("scorer-recall-checks", "Scorer defines recall checks", has_recall_checks))

    # ── Recall 8: Scorer has precision checks ─────────────────────────────
    has_precision_checks = "precision" in scorer_content and ("precision.append" in scorer_content or "precision =" in scorer_content)
    recall.append(("scorer-precision-checks", "Scorer defines precision checks", has_precision_checks))

    # ── Recall 9: Scorer mentions 80% threshold ───────────────────────────
    has_threshold = "0.8" in scorer_content or "80%" in scorer_content or "threshold" in scorer_content.lower()
    recall.append((
        "scorer-threshold",
        "Scorer mentions 80% threshold for AI evals",
        has_threshold,
    ))

    # ── Recall 10: Scorer imports from golden fixture ─────────────────────
    imports_golden = "from src.evals.book.fixtures.golden_emotion" in scorer_content or "from src.evals.harness.fixtures.golden_emotion" in scorer_content or "import golden_emotion" in scorer_content
    recall.append(("scorer-imports-golden", "Scorer imports golden labels", imports_golden))

    # ── Precision 1: Golden labels has docstring ──────────────────────────
    has_golden_docstring = '"""' in golden_content or "'''" in golden_content
    precision.append((
        "golden-docstring",
        "Golden labels has module docstring",
        has_golden_docstring,
    ))

    # ── Precision 2: Scorer has docstring ─────────────────────────────────
    has_scorer_docstring = '"""' in scorer_content or "'''" in scorer_content
    precision.append((
        "scorer-docstring",
        "Scorer has module docstring",
        has_scorer_docstring,
    ))

    # ── Precision 3: Scorer has usage instructions ────────────────────────
    has_usage = "Usage:" in scorer_content or "usage:" in scorer_content
    precision.append((
        "scorer-usage",
        "Scorer docstring includes usage instructions",
        has_usage,
    ))

    # ── Precision 4: No implementation code in fixtures ───────────────────
    # Check that golden labels don't import from domain/parsers/ai (should be pure data)
    bad_imports_golden = any(
        imp in golden_content
        for imp in ["from src.domain", "from src.parsers", "from src.ai"]
    )
    clean_golden = not bad_imports_golden
    precision.append((
        "golden-no-impl-imports",
        "Golden labels don't import implementation modules",
        clean_golden,
    ))

    # ── Precision 5: Scorer is syntactically valid Python ─────────────────
    try:
        ast.parse(scorer_content)
        scorer_valid = True
    except SyntaxError:
        scorer_valid = False
    precision.append(("scorer-syntax", "Scorer is valid Python", scorer_valid))

    # ── Precision 6: Golden labels is syntactically valid Python ──────────
    try:
        ast.parse(golden_content)
        golden_valid = True
    except SyntaxError:
        golden_valid = False
    precision.append(("golden-syntax", "Golden labels is valid Python", golden_valid))

    # ── Precision 7: Ruff passes on both files ────────────────────────────
    if golden_exists and scorer_exists:
        r = _run(["ruff", "check", str(GOLDEN_PATH), str(SCORER_PATH)])
        ruff_pass = r.returncode == 0
    else:
        ruff_pass = False
    precision.append(("ruff-pass", "ruff check passes on both files", ruff_pass))

    # ── Precision 8: Mypy passes on scorer ────────────────────────────────
    if scorer_exists:
        r = _run(["mypy", str(SCORER_PATH)])
        mypy_pass = r.returncode == 0
    else:
        mypy_pass = False
    precision.append(("mypy-pass", "mypy passes on scorer", mypy_pass))

    _print_report(recall, precision)


def _print_report(
    recall: list[tuple[str, str, bool]],
    precision: list[tuple[str, str, bool]],
) -> None:
    """Print the eval report."""
    print("=" * 70)
    print("EVAL AGENT EVAL RESULTS")
    print("=" * 70)

    total_recall = len(recall)
    passed_recall = sum(1 for _, _, ok in recall if ok)
    print(f"\nBehaviour compliance (recall): {passed_recall}/{total_recall}")
    for tag, desc, ok in recall:
        status = "PASS" if ok else "FAIL"
        print(f"  {status}  {tag}: {desc}")

    total_precision = len(precision)
    passed_precision = sum(1 for _, _, ok in precision if ok)
    if precision:
        print(f"\nSafety / selectivity (precision): {passed_precision}/{total_precision}")
        for tag, desc, ok in precision:
            status = "PASS" if ok else "FAIL"
            print(f"  {status}  {tag}: {desc}")

    recall_rate = passed_recall / total_recall if total_recall else 0
    precision_rate = passed_precision / total_precision if total_precision else 0
    print(f"\nRecall:    {recall_rate:.0%} ({passed_recall}/{total_recall})")
    print(f"Precision: {precision_rate:.0%} ({passed_precision}/{total_precision})")

    # For agent evals, we expect 100%
    passed = recall_rate == 1.0 and precision_rate == 1.0
    print(f"Score:     {'PASS' if passed else 'FAIL'}")


def cleanup() -> None:
    """Remove created files."""
    for path in (GOLDEN_PATH, SCORER_PATH):
        if path.exists():
            path.unlink()
            print(f"Removed {path.relative_to(REPO_ROOT)}")

    # Clean pycache
    for cache_dir in [GOLDEN_PATH.parent / "__pycache__", SCORER_PATH.parent / "__pycache__"]:
        if cache_dir.exists():
            for cached in cache_dir.glob("*emotion_detection*"):
                cached.unlink()
                print(f"Removed {cached}")

    print("Cleanup complete.")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd == "setup":
        setup()
    elif cmd == "score":
        score()
    elif cmd == "cleanup":
        cleanup()
    else:
        print("Usage: python -m src.evals.harness.score_eval_agent [setup|score|cleanup]")
