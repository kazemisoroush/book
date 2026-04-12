"""Scorer for the Dead Code Remover eval.

Usage:
    python -m src.evals.harness.score_dead_code_remover setup
    # run the Dead Code Remover agent
    python -m src.evals.harness.score_dead_code_remover score
    python -m src.evals.harness.score_dead_code_remover cleanup
"""
import re
import shutil
import sys
from pathlib import Path

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures"
MODULE_SRC = FIXTURE_DIR / "planted_dead_code.py"
TEST_SRC = FIXTURE_DIR / "planted_dead_code_test.py"
MODULE_DST = Path(__file__).parent.parent.parent / "domain" / "planted_dead_code_eval.py"
TEST_DST = Path(__file__).parent.parent.parent / "domain" / "planted_dead_code_eval_test.py"

# Ground truth: symbols/lines tagged in the fixture source.
# Each entry: (category, identifier_pattern, should_be_removed)
EXPECTATIONS = [
    ("unused-import",       "import os",              True),
    ("unused-import",       "import re",              False),
    ("unused-import",       "from dataclasses",       False),
    ("dead-function",       "def _legacy_parser",     True),
    ("live-function",       "def normalize_whitespace", False),
    ("live-function",       "def compute_stats",      False),
    ("live-class",          "class HelperResult",     False),
    ("unused-local",        "unused_temp",            True),
    ("unreachable",         "dead_line",              True),
    ("commented-code",      "def old_transform",      True),
]


def _strip_eval_metadata(source: str) -> str:
    """Remove eval tags so the planted file looks like ordinary code."""
    # Replace the entire module docstring with a neutral one
    result = re.sub(
        r'"""Planted dead code.*?"""',
        '"""Utility helpers for domain text processing."""',
        source,
        count=1,
        flags=re.DOTALL,
    )
    # Strip DEAD/LIVE trailing comments
    result = re.sub(r'\s*#\s*(?:DEAD|LIVE)\s*—.*$', '', result, flags=re.MULTILINE)
    return result


def setup() -> None:
    """Plant dead code module and its test file into domain/."""
    cleaned = _strip_eval_metadata(MODULE_SRC.read_text())
    MODULE_DST.write_text(cleaned)
    shutil.copy2(TEST_SRC, TEST_DST)
    print(f"Planted module at {MODULE_DST}")
    print(f"Planted tests  at {TEST_DST}")
    print("Now run the Dead Code Remover agent, then: python -m src.evals.harness.score_dead_code_remover score")


def score() -> None:
    """Check which dead symbols were removed and which live symbols survived."""
    if not MODULE_DST.exists():
        print("ERROR: planted module was deleted entirely. Agent should edit, not delete files.")
        return

    content = MODULE_DST.read_text()

    removed_dead = []
    missed_dead = []
    kept_live = []
    killed_live = []

    for category, pattern, should_remove in EXPECTATIONS:
        present = pattern in content
        if should_remove:
            if not present:
                removed_dead.append((category, pattern))
            else:
                missed_dead.append((category, pattern))
        else:
            if present:
                kept_live.append((category, pattern))
            else:
                killed_live.append((category, pattern))

    total_dead = sum(1 for _, _, r in EXPECTATIONS if r)
    total_live = sum(1 for _, _, r in EXPECTATIONS if not r)

    print("=" * 50)
    print("DEAD CODE REMOVER EVAL RESULTS")
    print("=" * 50)

    print(f"\nDead code removal (recall): {len(removed_dead)}/{total_dead}")
    for cat, pat in sorted(removed_dead):
        print(f"  PASS  {cat}: '{pat}' removed")
    for cat, pat in sorted(missed_dead):
        print(f"  FAIL  {cat}: '{pat}' still present")

    print(f"\nLive code preservation (precision): {len(kept_live)}/{total_live}")
    for cat, pat in sorted(kept_live):
        print(f"  PASS  {cat}: '{pat}' kept")
    for cat, pat in sorted(killed_live):
        print(f"  FAIL  {cat}: '{pat}' removed (was live)")

    recall = len(removed_dead) / total_dead if total_dead else 0
    precision = len(kept_live) / total_live if total_live else 0
    print(f"\nRecall:    {recall:.0%} ({len(removed_dead)}/{total_dead} dead symbols removed)")
    print(f"Precision: {precision:.0%} ({len(kept_live)}/{total_live} live symbols kept)")
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
        print("Usage: python -m src.evals.harness.score_dead_code_remover [setup|score|cleanup]")
