"""Scorer for the Orchestrator agent eval.

Gives the Orchestrator a small, self-contained spec (TextStats utility)
and checks whether it followed its workflow correctly:

  1. Delegated to Test Agent (test file exists with proper structure)
  2. Delegated to Coder Agent (implementation file exists, tests pass)
  3. Ran verification (lint + type checks pass)
  4. Produced a working feature (acceptance criteria met)
  5. Opened a PR on a feature branch with Co-Authored-By (not pushed to main)
  6. Archived the spec (moved from docs/specs/ to docs/specs/done/)

The eval cannot directly observe sub-agent dispatches, but it can
verify the *consequences* of correct orchestration:
  - TDD was followed: test file has AAA structure, tests are meaningful
  - Implementation is minimal: no extra public functions beyond spec
  - Check suite is green: pytest, ruff, mypy all pass
  - Feature works: acceptance criteria verified programmatically
  - Delivery: PR opened on feat/fix branch, main untouched

Usage:
    # 1. Plant the spec and record baseline
    python -m src.evals.score_orchestrator setup

    # 2. Run the Orchestrator agent with:
    #    "Execute the spec at docs/specs/planted_orchestrator_spec.md.
    #     Skip the audit hook."
    #
    #    The Orchestrator should open a PR and archive the spec without
    #    being told — that's what Phase 5 and the hard rules enforce.
    #    The Orchestrator must NOT run e2e pipeline tests (hard rule).

    # 3. Score the results
    python -m src.evals.score_orchestrator score

    # 4. Clean up (closes PR, deletes branch, removes files)
    python -m src.evals.score_orchestrator cleanup
"""
import ast
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
SPEC_PATH = Path(__file__).parent / "fixtures" / "planted_orchestrator_spec.md"
PLANTED_SPEC_ACTIVE = REPO_ROOT / "docs" / "specs" / "planted_orchestrator_spec.md"
PLANTED_SPEC_DONE = REPO_ROOT / "docs" / "specs" / "done" / "planted_orchestrator_spec.md"
IMPL_PATH = REPO_ROOT / "src" / "domain" / "eval_orchestrator_target.py"
TEST_PATH = REPO_ROOT / "src" / "domain" / "eval_orchestrator_target_test.py"
STATE_FILE = REPO_ROOT / ".claude" / "eval_orchestrator_state.json"


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)


def _git(cmd: str) -> str:
    """Run a git command and return stripped stdout."""
    return _run(cmd.split()).stdout.strip()


def setup() -> None:
    """Ensure the spec exists, no leftovers, and record baseline git state."""
    # Clean up any leftover files
    for path in (IMPL_PATH, TEST_PATH, PLANTED_SPEC_ACTIVE, PLANTED_SPEC_DONE):
        if path.exists():
            path.unlink()
            print(f"  cleaned  {path.relative_to(REPO_ROOT)}")

    # Plant the spec into docs/specs/ so Orchestrator can archive it to done/
    shutil.copy2(SPEC_PATH, PLANTED_SPEC_ACTIVE)
    print(f"  planted  {PLANTED_SPEC_ACTIVE.relative_to(REPO_ROOT)}")

    # Record baseline: main branch HEAD and current branch
    main_head = _git("git rev-parse main")
    remote_main_head = _git("git rev-parse origin/main")
    current_branch = _git("git branch --show-current")

    state = {
        "main_head_before": main_head,
        "remote_main_head_before": remote_main_head,
        "branch_before": current_branch,
    }
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))

    print(f"  spec at  {PLANTED_SPEC_ACTIVE.relative_to(REPO_ROOT)}")
    print(f"  main at  {main_head[:8]}")
    print()
    print("Setup complete. Now run the Orchestrator agent with a prompt like:")
    print(f'  "Execute the spec at {PLANTED_SPEC_ACTIVE.relative_to(REPO_ROOT)}.')
    print('   Skip the end-to-end test gate and skip the audit hook."')
    print()
    print("Then: python -m src.evals.score_orchestrator score")


def score() -> None:
    """Check if the Orchestrator produced the right files with the right quality."""
    recall: list[tuple[str, str, bool]] = []
    precision: list[tuple[str, str, bool]] = []

    # Load baseline state
    if STATE_FILE.exists():
        state = json.loads(STATE_FILE.read_text())
    else:
        state = {}

    # ── Recall 1: Test file exists ────────────────────────────────────
    test_exists = TEST_PATH.exists()
    recall.append(("test-file-exists", "Test file was created", test_exists))

    # ── Recall 2: Implementation file exists ──────────────────────────
    impl_exists = IMPL_PATH.exists()
    recall.append(("impl-file-exists", "Implementation file was created", impl_exists))

    if not test_exists or not impl_exists:
        _print_report(recall, precision)
        return

    test_content = TEST_PATH.read_text()
    impl_content = IMPL_PATH.read_text()

    # ── Recall 3: Test file has AAA structure ─────────────────────────
    has_aaa = (
        "# Arrange" in test_content
        and "# Act" in test_content
        and "# Assert" in test_content
    )
    recall.append(("test-aaa-structure", "Tests have Arrange/Act/Assert comments", has_aaa))

    # ── Recall 4: Test file has multiple test functions ───────────────
    test_tree = ast.parse(test_content)
    test_funcs = [
        node for node in ast.walk(test_tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    ]
    has_multiple_tests = len(test_funcs) >= 3
    recall.append((
        "multiple-tests",
        f"At least 3 test functions (got {len(test_funcs)})",
        has_multiple_tests,
    ))

    # ── Recall 5: Implementation has TextStats dataclass ──────────────
    has_textstats = "class TextStats" in impl_content
    recall.append(("has-textstats", "TextStats dataclass defined", has_textstats))

    # ── Recall 6: Implementation has compute_text_stats function ──────
    has_compute = "def compute_text_stats" in impl_content
    recall.append(("has-compute-fn", "compute_text_stats function defined", has_compute))

    # ── Recall 7: Tests pass ──────────────────────────────────────────
    r = _run(["pytest", "-x", str(TEST_PATH), "--no-header", "-q"])
    tests_pass = r.returncode == 0
    recall.append(("tests-pass", "All tests pass", tests_pass))

    # ── Recall 8: Ruff passes on both files ───────────────────────────
    r = _run(["ruff", "check", str(IMPL_PATH), str(TEST_PATH)])
    ruff_pass = r.returncode == 0
    recall.append(("ruff-pass", "ruff check passes", ruff_pass))

    # ── Recall 9: mypy passes on implementation ───────────────────────
    r = _run(["mypy", str(IMPL_PATH)])
    mypy_pass = r.returncode == 0
    recall.append(("mypy-pass", "mypy passes", mypy_pass))

    # ── Recall 10: Acceptance criteria met programmatically ───────────
    acceptance_checks = _check_acceptance_criteria()
    for tag, desc, ok in acceptance_checks:
        recall.append((tag, desc, ok))

    # ── Recall 11: PR was opened ──────────────────────────────────────
    pr_url, pr_branch, pr_found = _find_eval_pr()
    recall.append(("pr-opened", f"PR opened ({pr_url or 'none found'})", pr_found))

    # ── Recall 12: PR is on a feat/ or fix/ branch ───────────────────
    correct_branch_prefix = (
        pr_branch.startswith("feat/") or pr_branch.startswith("fix/")
    ) if pr_branch else False
    recall.append((
        "branch-prefix",
        f"Branch uses feat/ or fix/ prefix ({pr_branch or 'n/a'})",
        correct_branch_prefix,
    ))

    # ── Recall 13: Commit has Co-Authored-By trailer ────────────────
    if pr_branch:
        log_result = _run([
            "git", "log", f"main..{pr_branch}", "--format=%B", "-1",
        ])
        has_coauthor = "Co-Authored-By:" in log_result.stdout
    else:
        has_coauthor = False
    recall.append((
        "co-authored-by",
        "Commit includes Co-Authored-By trailer",
        has_coauthor,
    ))

    # ── Recall 14: Spec moved to docs/specs/done/ ─────────────────────
    spec_archived = PLANTED_SPEC_DONE.exists() and not PLANTED_SPEC_ACTIVE.exists()
    recall.append((
        "spec-archived",
        "Spec moved from docs/specs/ to docs/specs/done/",
        spec_archived,
    ))

    # ── Precision 1: No extra public functions beyond spec ────────────
    impl_tree = ast.parse(impl_content)
    public_funcs = [
        node.name for node in ast.walk(impl_tree)
        if isinstance(node, ast.FunctionDef)
        and not node.name.startswith("_")
    ]
    expected_public = {"compute_text_stats"}
    extra_funcs = set(public_funcs) - expected_public
    no_extra_funcs = len(extra_funcs) == 0
    precision.append((
        "no-extra-funcs",
        f"No extra public functions (found: {extra_funcs or 'none'})",
        no_extra_funcs,
    ))

    # ── Precision 2: Implementation is frozen dataclass ───────────────
    has_frozen = "frozen=True" in impl_content or "frozen = True" in impl_content
    precision.append(("frozen-dataclass", "TextStats is frozen", has_frozen))

    # ── Precision 3: Full test suite still passes ─────────────────────
    r = _run(["pytest", "--no-header", "-q", "--ignore=src/evals/fixtures"])
    full_suite = r.returncode == 0
    precision.append(("full-suite-passes", "Full pytest suite still passes", full_suite))

    # ── Precision 4: Test file does NOT import from wrong layers ──────
    bad_imports = any(
        imp in test_content
        for imp in ["from src.ai", "from src.tts", "from src.workflows", "from src.parsers"]
    )
    clean_imports = not bad_imports
    precision.append(("clean-test-imports", "Tests import only from domain layer", clean_imports))

    # ── Precision 5: main branch was NOT pushed to directly ───────────
    if state:
        remote_main_now = _git("git rev-parse origin/main")
        main_untouched = remote_main_now == state["remote_main_head_before"]
    else:
        main_untouched = True  # Can't check without baseline
    precision.append((
        "main-untouched",
        "origin/main was not pushed to directly",
        main_untouched,
    ))

    _print_report(recall, precision)


def _find_eval_pr() -> tuple[str | None, str | None, bool]:
    """Find an open PR created by the Orchestrator for this eval.

    Searches open PRs for one that touches eval_orchestrator_target files,
    matches TextStats keywords, or sits on a feat/fix branch created after
    the baseline was recorded.

    Returns (pr_url, branch_name, found).
    """
    r = _run([
        "gh", "pr", "list",
        "--state", "open",
        "--json", "url,headRefName,title,files",
        "--limit", "10",
    ])
    if r.returncode != 0:
        return None, None, False

    try:
        prs = json.loads(r.stdout)
    except json.JSONDecodeError:
        return None, None, False

    # Priority 1: PR that touches the eval target files
    target_files = {"src/domain/eval_orchestrator_target.py",
                    "src/domain/eval_orchestrator_target_test.py"}
    for pr in prs:
        pr_files = {f.get("path", "") for f in pr.get("files", [])}
        if pr_files & target_files:
            return pr["url"], pr["headRefName"], True

    # Priority 2: PR with TextStats-related keywords in title or branch
    keywords = ["textstats", "text_stats", "text-stats",
                "eval_orchestrator", "eval-orchestrator"]
    for pr in prs:
        title_lower = pr.get("title", "").lower()
        branch_lower = pr.get("headRefName", "").lower()
        if any(kw in title_lower or kw in branch_lower for kw in keywords):
            return pr["url"], pr["headRefName"], True

    # Priority 3: any PR on a feat/ or fix/ branch (loose fallback)
    for pr in prs:
        branch = pr.get("headRefName", "")
        if branch.startswith("feat/") or branch.startswith("fix/"):
            return pr["url"], branch, True

    return None, None, False


def _check_acceptance_criteria() -> list[tuple[str, str, bool]]:
    """Verify acceptance criteria by importing and running the implementation."""
    checks: list[tuple[str, str, bool]] = []

    try:
        import importlib
        mod = importlib.import_module("src.domain.eval_orchestrator_target")
        importlib.reload(mod)

        compute = getattr(mod, "compute_text_stats", None)
        text_stats_cls = getattr(mod, "TextStats", None)

        if compute is None or text_stats_cls is None:
            checks.append(("ac-imports", "Can import TextStats and compute_text_stats", False))
            return checks
        checks.append(("ac-imports", "Can import TextStats and compute_text_stats", True))

        # AC2: basic computation
        result = compute("Hello world. How are you?")
        ac2 = (
            result.word_count == 5
            and result.sentence_count == 2
        )
        checks.append(("ac-basic", f"Basic: 5 words, 2 sentences (got {result.word_count}w, {result.sentence_count}s)", ac2))

        # AC3: sentence splitting on . ! ?
        result2 = compute("Wow! Really? Yes.")
        ac3 = result2.sentence_count == 3
        checks.append(("ac-sentences", f"Splits on .!? → 3 sentences (got {result2.sentence_count})", ac3))

        # AC5: avg_word_length rounded to 1 decimal
        result3 = compute("hi there")  # hi=2, there=5 → avg 3.5
        ac5 = result3.avg_word_length == 3.5
        checks.append(("ac-avg-length", f"avg_word_length rounded to 1dp (got {result3.avg_word_length})", ac5))

        # AC6: empty string
        result4 = compute("")
        ac6 = (
            result4.word_count == 0
            and result4.sentence_count == 0
            and result4.avg_word_length == 0.0
        )
        checks.append(("ac-empty", f"Empty string → all zeros (got {result4})", ac6))

    except Exception as e:
        checks.append(("ac-runtime", f"Runtime error: {e}", False))

    return checks


def _print_report(
    recall: list[tuple[str, str, bool]],
    precision: list[tuple[str, str, bool]],
) -> None:
    """Print the eval report."""
    print("=" * 55)
    print("ORCHESTRATOR EVAL RESULTS")
    print("=" * 55)

    total_recall = len(recall)
    passed_recall = sum(1 for _, _, ok in recall if ok)
    print(f"\nOrchestration quality (recall): {passed_recall}/{total_recall}")
    for tag, desc, ok in recall:
        status = "PASS" if ok else "FAIL"
        print(f"  {status}  {tag}: {desc}")

    total_precision = len(precision)
    passed_precision = sum(1 for _, _, ok in precision if ok)
    if precision:
        print(f"\nImplementation discipline (precision): {passed_precision}/{total_precision}")
        for tag, desc, ok in precision:
            status = "PASS" if ok else "FAIL"
            print(f"  {status}  {tag}: {desc}")

    recall_rate = passed_recall / total_recall if total_recall else 0
    precision_rate = passed_precision / total_precision if total_precision else 0
    print(f"\nRecall:    {recall_rate:.0%} ({passed_recall}/{total_recall})")
    print(f"Precision: {precision_rate:.0%} ({passed_precision}/{total_precision})")
    print(f"Score:     {'PASS' if recall_rate == 1.0 and precision_rate == 1.0 else 'FAIL'}")


def cleanup() -> None:
    """Close PR, delete branch, remove files."""
    # Find and close the eval PR
    pr_url, pr_branch, pr_found = _find_eval_pr()
    if pr_found and pr_url:
        # Close the PR
        _run(["gh", "pr", "close", pr_url, "--delete-branch"])
        print(f"Closed PR: {pr_url}")
        print(f"Deleted branch: {pr_branch}")

    # Switch back to main if we're on a feature branch
    current = _git("git branch --show-current")
    if current != "main":
        _run(["git", "checkout", "main"])
        print("Switched back to main")

    # Delete local branch if it still exists
    if pr_branch:
        _run(["git", "branch", "-D", pr_branch])

    # Remove created files
    for path in (IMPL_PATH, TEST_PATH, PLANTED_SPEC_ACTIVE, PLANTED_SPEC_DONE):
        if path.exists():
            path.unlink()
            print(f"Removed {path}")

    # Remove state file
    if STATE_FILE.exists():
        STATE_FILE.unlink()
        print(f"Removed {STATE_FILE}")

    # Clean pycache
    cache_dir = IMPL_PATH.parent / "__pycache__"
    if cache_dir.exists():
        for cached in cache_dir.glob("eval_orchestrator_target*"):
            cached.unlink()
            print(f"Removed {cached}")

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
        print("Usage: python -m src.evals.score_orchestrator [setup|score|cleanup]")
