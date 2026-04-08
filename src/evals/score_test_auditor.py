"""Scorer for the Test Auditor eval.

Usage:
    # 1. Copy the fixture into place
    python -m src.evals.score_test_auditor setup

    # 2. Run the Test Auditor agent (manually via /audit or the test-auditor agent)

    # 3. Score the results
    python -m src.evals.score_test_auditor score
"""
import ast
import sys
from pathlib import Path

FIXTURE_SRC = Path(__file__).parent / "fixtures" / "planted_violations.py"
FIXTURE_DST = Path(__file__).parent.parent / "domain" / "planted_violations_test.py"


def _parse_classes(path: Path) -> dict[str, str]:
    """Return {ClassName: first_line_of_docstring} for every class in the file."""
    if not path.exists():
        return {}
    tree = ast.parse(path.read_text())
    result = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            docstring = ast.get_docstring(node) or ""
            result[node.name] = docstring.split("\n")[0]
    return result


def _count_test_methods(path: Path) -> dict[str, int]:
    """Return {ClassName: number_of_test_methods} for every class in the file."""
    if not path.exists():
        return {}
    tree = ast.parse(path.read_text())
    result = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            count = sum(
                1 for item in node.body
                if isinstance(item, ast.FunctionDef) and item.name.startswith("test_")
            )
            result[node.name] = count
    return result


def _strip_eval_metadata(source: str) -> str:
    """Remove eval-specific markers so the planted file looks like ordinary tests."""
    lines = source.split("\n")
    cleaned = []
    for line in lines:
        # Strip SHOULD_DELETE / SHOULD_SURVIVE / SHOULD_MERGE from class docstrings
        if "SHOULD_DELETE" in line or "SHOULD_SURVIVE" in line or "SHOULD_MERGE" in line:
            # Keep just the rule tag as an innocent comment-style docstring
            line = line.replace("SHOULD_DELETE | ", "").replace("SHOULD_SURVIVE | ", "").replace("SHOULD_MERGE | ", "")
        cleaned.append(line)
    # Replace the module docstring with something neutral
    result = "\n".join(cleaned)
    result = result.replace(
        ast.get_docstring(ast.parse(source)) or "",
        "Tests for domain model edge cases.",
    )
    return result


def setup() -> None:
    """Copy planted violations into domain/ where the Test Auditor will find them."""
    source = FIXTURE_SRC.read_text()
    cleaned = _strip_eval_metadata(source)
    FIXTURE_DST.write_text(cleaned)
    print(f"Planted fixture at {FIXTURE_DST}")
    print("Now run the Test Auditor agent, then: python -m src.evals.score_test_auditor score")


def score() -> None:
    """Compare surviving test classes against expected outcomes."""
    # What we planted (ground truth)
    original = _parse_classes(FIXTURE_SRC)
    original_method_counts = _count_test_methods(FIXTURE_SRC)
    should_delete = {name for name, doc in original.items() if "SHOULD_DELETE" in doc}
    should_survive = {name for name, doc in original.items() if "SHOULD_SURVIVE" in doc}
    should_merge = {name for name, doc in original.items() if "SHOULD_MERGE" in doc}

    # What remains after the auditor ran
    surviving = set(_parse_classes(FIXTURE_DST).keys())
    surviving_method_counts = _count_test_methods(FIXTURE_DST)

    # If the auditor deleted the entire file, all classes are gone
    if not FIXTURE_DST.exists():
        surviving = set()
        surviving_method_counts = {}

    # Score — deletions
    correctly_deleted = should_delete - surviving
    missed_violations = should_delete & surviving
    correctly_kept = should_survive & surviving
    false_positives = should_survive - surviving

    # Score — merges (class must survive but with fewer test methods)
    merge_pass = set()
    merge_fail = set()
    for name in should_merge:
        orig_count = original_method_counts.get(name, 0)
        new_count = surviving_method_counts.get(name, 0)
        if name not in surviving:
            merge_fail.add(name)  # Class deleted entirely — wrong
        elif new_count < orig_count:
            merge_pass.add(name)  # Merged: fewer methods
        else:
            merge_fail.add(name)  # Not merged: same or more methods

    total_rules = len(should_delete)
    total_clean = len(should_survive)
    total_merge = len(should_merge)

    print("=" * 50)
    print("TEST AUDITOR EVAL RESULTS")
    print("=" * 50)

    print(f"\nViolation detection (recall): {len(correctly_deleted)}/{total_rules}")
    for name in sorted(correctly_deleted):
        rule = original[name].split("rule:")[1] if "rule:" in original[name] else "?"
        print(f"  PASS  {rule}: {name} deleted")
    for name in sorted(missed_violations):
        rule = original[name].split("rule:")[1] if "rule:" in original[name] else "?"
        print(f"  FAIL  {rule}: {name} survived (should have been deleted)")

    print(f"\nClean test preservation (precision): {len(correctly_kept)}/{total_clean}")
    for name in sorted(correctly_kept):
        print(f"  PASS  {name} kept")
    for name in sorted(false_positives):
        print(f"  FAIL  {name} deleted (was clean)")

    print(f"\nMerge detection: {len(merge_pass)}/{total_merge}")
    for name in sorted(merge_pass):
        orig = original_method_counts.get(name, 0)
        now = surviving_method_counts.get(name, 0)
        print(f"  PASS  {name}: {orig} methods → {now} (merged)")
    for name in sorted(merge_fail):
        if name not in surviving:
            print(f"  FAIL  {name}: class deleted entirely (should have been merged)")
        else:
            orig = original_method_counts.get(name, 0)
            now = surviving_method_counts.get(name, 0)
            print(f"  FAIL  {name}: {orig} methods → {now} (not merged)")

    recall = len(correctly_deleted) / total_rules if total_rules else 0
    precision = len(correctly_kept) / total_clean if total_clean else 0
    merge_rate = len(merge_pass) / total_merge if total_merge else 0
    print(f"\nRecall:    {recall:.0%} ({len(correctly_deleted)}/{total_rules} violations caught)")
    print(f"Precision: {precision:.0%} ({len(correctly_kept)}/{total_clean} clean tests kept)")
    print(f"Merge:     {merge_rate:.0%} ({len(merge_pass)}/{total_merge} near-duplicates merged)")
    all_pass = recall == 1.0 and precision == 1.0 and merge_rate == 1.0
    print(f"Score:     {'PASS' if all_pass else 'FAIL'}")


def cleanup() -> None:
    """Remove the planted fixture from domain/."""
    if FIXTURE_DST.exists():
        FIXTURE_DST.unlink()
        print(f"Removed {FIXTURE_DST}")
    else:
        print("Nothing to clean up.")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd == "setup":
        setup()
    elif cmd == "score":
        score()
    elif cmd == "cleanup":
        cleanup()
    else:
        print("Usage: python -m src.evals.score_test_auditor [setup|score|cleanup]")
