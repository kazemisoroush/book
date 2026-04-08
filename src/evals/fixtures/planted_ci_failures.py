"""Planted CI failures — broken code for the CI/CD Fixer eval.

NOT a real module. The eval scorer copies this into src/domain/ as a
real .py file at setup time, stripping eval metadata comments.

The planted module has three deliberate failures:
  1. LINT  — unused import (ruff will flag)
  2. TYPE  — wrong return type annotation (mypy will flag)
  3. TEST  — logic bug that causes a test failure (pytest will flag)

Each line with a bug is tagged:
  # BUG:LINT  — ruff failure
  # BUG:TYPE  — mypy failure
  # BUG:TEST  — pytest failure
  # CLEAN     — must not be changed
"""
import json  # BUG:LINT — unused import, ruff F401
import re  # CLEAN — used by strip_markup


def strip_markup(text: str) -> str:  # CLEAN
    """Remove angle-bracket markup tags from text."""
    return re.sub(r"<[^>]+>", "", text)


def word_count(text: str) -> int:  # BUG:TYPE — annotation says int, returns str
    """Return the number of words in text."""
    words = text.split()
    return str(len(words))  # BUG:TYPE — returns str, not int


def double_value(n: int) -> int:  # BUG:TEST — triples instead of doubles
    """Return n doubled."""
    return n * 3  # BUG:TEST — should be n * 2
