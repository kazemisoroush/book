"""Planted dead code — one example per Dead Code Remover category.

NOT a real module. The eval scorer copies this into src/domain/ as
a real .py file at setup time, stripping eval metadata.

Each symbol is tagged in a trailing comment:
  # DEAD — should be removed by the Dead Code Remover
  # LIVE — must survive (used by the companion _test.py or within this file)

Categories covered:
  1. Unused import
  2. Unreferenced module-level function
  3. Unreachable branch
  4. Unused local variable
  5. Commented-out code block
"""
import os  # DEAD — unused import
import re  # LIVE — used by normalize_whitespace

from dataclasses import dataclass  # LIVE — used by HelperResult


@dataclass
class HelperResult:  # LIVE — used by normalize_whitespace return type
    """A small result wrapper used by normalize_whitespace."""
    text: str
    changed: bool


def _legacy_parser(raw: str) -> str:  # DEAD — unreferenced module-level function
    """Old parser that was replaced. Nobody calls this."""
    return raw.upper()


def normalize_whitespace(text: str) -> HelperResult:  # LIVE — exported, tested
    """Collapse runs of whitespace to a single space."""
    cleaned = re.sub(r'\s+', ' ', text.strip())
    return HelperResult(text=cleaned, changed=cleaned != text)


def compute_stats(text: str) -> dict[str, int]:  # LIVE — exported, tested
    """Return basic character counts."""
    unused_temp = 42  # DEAD — unused local variable
    words = text.split()
    if not words:
        return {"words": 0, "chars": 0}
        dead_line = True  # DEAD — unreachable branch (after return)
    return {"words": len(words), "chars": len(text)}


# DEAD — commented-out code block (5 lines of valid Python)
# def old_transform(s: str) -> str:
#     """Transform that was removed in v2."""
#     parts = s.split(",")
#     joined = " ".join(parts)
#     return joined.strip()
