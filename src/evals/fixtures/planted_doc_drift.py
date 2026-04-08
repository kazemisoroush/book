"""Planted documentation drift — one example per Doc Auditor category.

NOT a real module. The eval scorer copies this into src/domain/ at setup
time, stripping eval metadata.

Each drift is tagged in a comment:
  # DRIFT:stale-name — docstring uses old name, code uses new name
  # DRIFT:missing-entry — public function not mentioned in docstring
  # DRIFT:removed-entry — docstring mentions function that doesn't exist
  # DRIFT:stale-signature — docstring shows wrong parameters
  # CORRECT — docstring entry matches code, must survive editing
"""

# ---- The MODULE DOCSTRING below is the target the Doc Auditor should fix ----
# It will be injected by the scorer's setup as the file's actual docstring.
# We store it here as a constant so we can also parse it for scoring.

MODULE_DOCSTRING = '''"""Helpers for text chunk processing.

Public API:

- ``split_text(text)`` — split text into sentences  # DRIFT:stale-name (actual function is split_into_sentences)
- ``count_words(text) -> int`` — count words in text  # CORRECT (matches code exactly)
- ``merge_chunks(chunks, separator) -> str`` — merge chunks with separator  # DRIFT:stale-signature (actual signature has no separator param)
- ``normalize_case(text) -> str`` — normalize text to lowercase  # DRIFT:removed-entry (function does not exist)
(missing: deduplicate_chunks is a public function not listed here)  # DRIFT:missing-entry
"""'''

# ---- Actual code (ground truth) ----

def split_into_sentences(text: str) -> list[str]:  # DRIFT:stale-name — docstring says split_text
    """Split text into sentences on period boundaries."""
    return [s.strip() for s in text.split(".") if s.strip()]


def count_words(text: str) -> int:  # CORRECT — docstring matches
    """Count words in text."""
    return len(text.split())


def merge_chunks(chunks: list[str]) -> str:  # DRIFT:stale-signature — docstring adds separator param
    """Merge chunks with a space."""
    return " ".join(chunks)


def deduplicate_chunks(chunks: list[str]) -> list[str]:  # DRIFT:missing-entry — not in docstring
    """Remove duplicate chunks preserving order."""
    seen: set[str] = set()
    result = []
    for chunk in chunks:
        if chunk not in seen:
            seen.add(chunk)
            result.append(chunk)
    return result
