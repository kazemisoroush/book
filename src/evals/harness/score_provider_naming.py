"""Scorer for the Orchestrator provider-naming eval.

Gives the Orchestrator a spec that requires creating a TTSProvider
implementation and checks whether the naming convention was followed:

  1. File named {vendor}_{capability}_provider.py (not {vendor}_provider.py)
  2. Class named {Vendor}{Capability}Provider (not {Vendor}Provider)
  3. Test file named {vendor}_{capability}_provider_test.py
  4. Class is a subclass of TTSProvider
  5. Standard orchestration checks (TDD, lint, tests pass, PR, spec archived)

Cost: $0 (no API calls — exercises the Orchestrator/Test Agent/Coder Agent)

Usage:
    # 1. Plant the spec and record baseline
    python -m src.evals.harness.score_provider_naming setup

    # 2. Run the Orchestrator agent with:
    #    "Execute the spec at docs/specs/planted_provider_naming_spec.md.
    #     Skip the audit hook."

    # 3. Score the results
    python -m src.evals.harness.score_provider_naming score

    # 4. Clean up (closes PR, deletes branch, removes files)
    python -m src.evals.harness.score_provider_naming cleanup
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent.parent
SPEC_PATH = Path(__file__).parent / "fixtures" / "planted_provider_naming_spec.md"
PLANTED_SPEC_ACTIVE = REPO_ROOT / "docs" / "specs" / "planted_provider_naming_spec.md"
PLANTED_SPEC_DONE = REPO_ROOT / "docs" / "specs" / "done" / "planted_provider_naming_spec.md"

# Expected paths if naming convention is followed
IMPL_PATH = REPO_ROOT / "src" / "tts" / "local_tts_provider.py"
TEST_PATH = REPO_ROOT / "src" / "tts" / "local_tts_provider_test.py"

# Wrong paths if naming convention is violated
BAD_IMPL_PATH = REPO_ROOT / "src" / "tts" / "local_provider.py"
BAD_TEST_PATH = REPO_ROOT / "src" / "tts" / "local_provider_test.py"

STATE_FILE = REPO_ROOT / ".claude" / "eval_provider_naming_state.json"


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)


def _git(cmd: str) -> str:
    """Run a git command and return stripped stdout."""
    return _run(cmd.split()).stdout.strip()


def setup() -> None:
    """Plant the spec, clean leftovers, record baseline."""
    # Clean up any leftover files
    for path in (
        IMPL_PATH, TEST_PATH, BAD_IMPL_PATH, BAD_TEST_PATH,
        PLANTED_SPEC_ACTIVE, PLANTED_SPEC_DONE,
    ):
        if path.exists():
            path.unlink()
            print(f"  cleaned  {path.relative_to(REPO_ROOT)}")

    # Plant the spec
    shutil.copy2(SPEC_PATH, PLANTED_SPEC_ACTIVE)
    print(f"  planted  {PLANTED_SPEC_ACTIVE.relative_to(REPO_ROOT)}")

    # Record baseline
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
    print("Setup complete. Now run the Orchestrator agent with:")
    print(f'  "Execute the spec at {PLANTED_SPEC_ACTIVE.relative_to(REPO_ROOT)}.')
    print('   Skip the audit hook."')
    print()
    print("Then: python -m src.evals.harness.score_provider_naming score")


def score() -> None:
    """Check naming convention compliance and standard orchestration quality."""
    recall: list[tuple[str, str, bool]] = []
    precision: list[tuple[str, str, bool]] = []

    # ── Recall 1: Implementation file exists with correct name ─────────
    impl_exists = IMPL_PATH.exists()
    recall.append((
        "impl-correct-name",
        "Implementation at local_tts_provider.py (not local_provider.py)",
        impl_exists,
    ))

    # ── Recall 2: Test file exists with correct name ───────────────────
    test_exists = TEST_PATH.exists()
    recall.append((
        "test-correct-name",
        "Test at local_tts_provider_test.py (not local_provider_test.py)",
        test_exists,
    ))

    if not impl_exists or not test_exists:
        # Check if files exist with wrong names
        if BAD_IMPL_PATH.exists():
            print(f"  NOTE: Found {BAD_IMPL_PATH.name} — wrong naming convention")
        if BAD_TEST_PATH.exists():
            print(f"  NOTE: Found {BAD_TEST_PATH.name} — wrong naming convention")
        _print_report(recall, precision)
        return

    impl_content = IMPL_PATH.read_text()
    test_content = TEST_PATH.read_text()

    # ── Recall 3: Class named LocalTTSProvider (not LocalProvider) ─────
    has_correct_class = "class LocalTTSProvider" in impl_content
    recall.append((
        "class-correct-name",
        "Class named LocalTTSProvider (not LocalProvider)",
        has_correct_class,
    ))

    # ── Recall 4: Subclass of TTSProvider ──────────────────────────────
    has_tts_parent = "TTSProvider" in impl_content and "class LocalTTSProvider" in impl_content
    recall.append((
        "subclass-tts-provider",
        "LocalTTSProvider inherits from TTSProvider",
        has_tts_parent,
    ))

    # ── Recall 5: synthesize() method exists ───────────────────────────
    has_synthesize = "def synthesize" in impl_content
    recall.append(("has-synthesize", "synthesize() method defined", has_synthesize))

    # ── Recall 6: get_available_voices() method exists ─────────────────
    has_voices = "def get_available_voices" in impl_content
    recall.append(("has-get-voices", "get_available_voices() method defined", has_voices))

    # ── Recall 7: Test file has AAA structure ──────────────────────────
    has_aaa = (
        "# Arrange" in test_content
        and "# Act" in test_content
        and "# Assert" in test_content
    )
    recall.append(("test-aaa-structure", "Tests have Arrange/Act/Assert comments", has_aaa))

    # ── Recall 8: Tests pass ───────────────────────────────────────────
    r = _run(["pytest", "-x", str(TEST_PATH), "--no-header", "-q"])
    tests_pass = r.returncode == 0
    recall.append(("tests-pass", "All tests pass", tests_pass))

    # ── Recall 9: Ruff passes ──────────────────────────────────────────
    r = _run(["ruff", "check", str(IMPL_PATH), str(TEST_PATH)])
    ruff_pass = r.returncode == 0
    recall.append(("ruff-pass", "ruff check passes", ruff_pass))

    # ── Recall 10: mypy passes ─────────────────────────────────────────
    r = _run(["mypy", str(IMPL_PATH)])
    mypy_pass = r.returncode == 0
    recall.append(("mypy-pass", "mypy passes", mypy_pass))

    # ── Recall 11: Acceptance criteria — get_available_voices returns correct dict
    try:
        import importlib
        mod = importlib.import_module("src.tts.local_tts_provider")
        importlib.reload(mod)
        cls = getattr(mod, "LocalTTSProvider", None)
        if cls is not None:
            instance = cls()
            voices = instance.get_available_voices()
            ac_voices = voices == {"default": "local-default"}
            recall.append((
                "ac-voices",
                f'get_available_voices() returns {{"default": "local-default"}} (got {voices})',
                ac_voices,
            ))
        else:
            recall.append(("ac-voices", "LocalTTSProvider class not found", False))
    except Exception as e:
        recall.append(("ac-voices", f"Runtime error: {e}", False))

    # ── Recall 12: Branch is rebased on main ────────────────────────────
    try:
        state = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
        main_head = state.get("main_head_before", "")
        if main_head:
            r = _run(["git", "merge-base", "--is-ancestor", main_head, "HEAD"])
            branch_rebased = r.returncode == 0
        else:
            branch_rebased = False
        recall.append((
            "branch-rebased",
            "Feature branch includes main HEAD recorded at setup",
            branch_rebased,
        ))
    except Exception:
        recall.append(("branch-rebased", "Could not check branch ancestry", False))

    # ── Recall 13: Spec archived ───────────────────────────────────────
    spec_archived = PLANTED_SPEC_DONE.exists() and not PLANTED_SPEC_ACTIVE.exists()
    recall.append((
        "spec-archived",
        "Spec moved from docs/specs/ to docs/specs/done/",
        spec_archived,
    ))

    # ── Precision 1: No wrong-name files created ───────────────────────
    no_bad_impl = not BAD_IMPL_PATH.exists()
    precision.append((
        "no-bad-impl-name",
        "No local_provider.py created (wrong naming)",
        no_bad_impl,
    ))

    no_bad_test = not BAD_TEST_PATH.exists()
    precision.append((
        "no-bad-test-name",
        "No local_provider_test.py created (wrong naming)",
        no_bad_test,
    ))

    # ── Precision 2: Class is NOT named LocalProvider ──────────────────
    has_bad_class = "class LocalProvider" in impl_content
    no_bad_class = not has_bad_class
    precision.append((
        "no-bad-class-name",
        "No class named LocalProvider (wrong naming)",
        no_bad_class,
    ))

    # ── Precision 3: No language-testing tests ─────────────────────────
    has_abc_test = "Can't instantiate abstract class" in test_content
    has_none_test = "assert provider is not None" in test_content or "assert instance is not None" in test_content
    no_language_tests = not has_abc_test and not has_none_test
    precision.append((
        "no-language-tests",
        "No ABC-instantiation or is-not-None tests",
        no_language_tests,
    ))

    # ── Precision 4: Full test suite still passes ──────────────────────
    r = _run(["pytest", "--no-header", "-q", "--ignore=src/evals/book/fixtures", "--ignore=src/evals/harness/fixtures"])
    full_suite = r.returncode == 0
    precision.append(("full-suite-passes", "Full pytest suite still passes", full_suite))

    # ── Precision 5: Import follows convention ─────────────────────────
    # Test file should import from local_tts_provider, not local_provider
    correct_import = "from src.tts.local_tts_provider" in test_content
    precision.append((
        "test-import-convention",
        "Test imports from local_tts_provider (correct module name)",
        correct_import,
    ))

    _print_report(recall, precision)


def _print_report(
    recall: list[tuple[str, str, bool]],
    precision: list[tuple[str, str, bool]],
) -> None:
    """Print the eval report."""
    print("=" * 55)
    print("PROVIDER NAMING EVAL RESULTS")
    print("=" * 55)

    total_recall = len(recall)
    passed_recall = sum(1 for _, _, ok in recall if ok)
    print(f"\nNaming convention + orchestration (recall): {passed_recall}/{total_recall}")
    for tag, desc, ok in recall:
        status = "PASS" if ok else "FAIL"
        print(f"  {status}  {tag}: {desc}")

    total_precision = len(precision)
    passed_precision = sum(1 for _, _, ok in precision if ok)
    if precision:
        print(f"\nDiscipline (precision): {passed_precision}/{total_precision}")
        for tag, desc, ok in precision:
            status = "PASS" if ok else "FAIL"
            print(f"  {status}  {tag}: {desc}")

    recall_rate = passed_recall / total_recall if total_recall else 0
    precision_rate = passed_precision / total_precision if total_precision else 0
    print(f"\nRecall:    {recall_rate:.0%} ({passed_recall}/{total_recall})")
    print(f"Precision: {precision_rate:.0%} ({passed_precision}/{total_precision})")
    print(f"Score:     {'PASS' if recall_rate == 1.0 and precision_rate == 1.0 else 'FAIL'}")


def cleanup() -> None:
    """Remove planted files, close PR, clean up."""
    # Find and close eval PR
    r = _run([
        "gh", "pr", "list",
        "--state", "open",
        "--json", "url,headRefName,title,files",
        "--limit", "10",
    ])
    if r.returncode == 0:
        try:
            prs = json.loads(r.stdout)
            target_files = {
                "src/tts/local_tts_provider.py",
                "src/tts/local_tts_provider_test.py",
            }
            for pr in prs:
                pr_files = {f.get("path", "") for f in pr.get("files", [])}
                if pr_files & target_files:
                    _run(["gh", "pr", "close", pr["url"], "--delete-branch"])
                    print(f"Closed PR: {pr['url']}")
                    print(f"Deleted branch: {pr['headRefName']}")
                    break
        except json.JSONDecodeError:
            pass

    # Switch back to main if needed
    current = _git("git branch --show-current")
    if current != "main":
        _run(["git", "checkout", "main"])
        print("Switched back to main")

    # Remove all possible created files
    for path in (
        IMPL_PATH, TEST_PATH, BAD_IMPL_PATH, BAD_TEST_PATH,
        PLANTED_SPEC_ACTIVE, PLANTED_SPEC_DONE,
    ):
        if path.exists():
            path.unlink()
            print(f"Removed {path.relative_to(REPO_ROOT)}")

    if STATE_FILE.exists():
        STATE_FILE.unlink()
        print(f"Removed {STATE_FILE.relative_to(REPO_ROOT)}")

    # Clean pycache
    cache_dir = IMPL_PATH.parent / "__pycache__"
    if cache_dir.exists():
        for cached in cache_dir.glob("local_tts_provider*"):
            cached.unlink()
            print(f"Removed {cached.relative_to(REPO_ROOT)}")
        for cached in cache_dir.glob("local_provider*"):
            cached.unlink()
            print(f"Removed {cached.relative_to(REPO_ROOT)}")

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
        print("Usage: python -m src.evals.harness.score_provider_naming [setup|score|cleanup]")
