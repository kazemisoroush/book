"""Section filter for removing junk sections from parsed book content.

This module is part of the parsers layer and may only import from domain
and below.

Junk section categories (per US-007):
1. Page number artifacts — text matching ``\\{\\d+\\}`` (e.g. ``{6}``, ``{12}``)
2. In-page copyright blocks — text matching ``\\[Copyright.*?\\]``
3. Illustration captions — short lines (< 60 chars) matching the pattern
   ``[A-Z][a-z]+ [&] [A-Z][a-z]+`` with no surrounding prose.
   These are NOT discarded; they are tagged ``section_type='illustration'``.
"""
import re
from src.domain.models import Section

# Pattern: bare page number artifact — the entire (stripped) text is {N}
_PAGE_NUMBER_RE = re.compile(r'^\{\d+\}$')

# Pattern: in-page copyright block — the entire (stripped) text is [Copyright ...]
_COPYRIGHT_RE = re.compile(r'^\[Copyright.*?\]$', re.DOTALL)

# Pattern: illustration caption — short (< 60 chars), matches "Word & Word" structure
# e.g. "Mr. & Mrs. Bennet", "Sir & Lady Fitzwilliam"
_ILLUSTRATION_CAPTION_RE = re.compile(
    r'^[A-Z][A-Za-z.]*(?:\s[A-Za-z.]+)*\s[&]\s[A-Z][A-Za-z.]*(?:\s[A-Za-z.]+)*$'
)
_ILLUSTRATION_MAX_LEN = 60


class SectionFilter:
    """Classifies and removes non-prose sections.

    - Page number artifacts and copyright blocks are dropped entirely.
    - Illustration captions are kept and tagged with section_type='illustration'.

    The filter is stateless and deterministic — no AI calls.
    """

    def filter(self, sections: list[Section]) -> list[Section]:
        """Filter a list of sections, removing junk and tagging illustrations.

        Args:
            sections: The list of :class:`~src.domain.models.Section` objects
                      to filter.

        Returns:
            A new list with junk sections removed and illustration sections
            tagged with ``section_type='illustration'``.
        """
        result: list[Section] = []
        for section in sections:
            stripped = section.text.strip()

            # Drop page number artifacts entirely
            if _PAGE_NUMBER_RE.match(stripped):
                continue

            # Drop in-page copyright blocks entirely
            if _COPYRIGHT_RE.match(stripped):
                continue

            # Tag illustration captions and keep them
            if (
                section.section_type is None
                and len(stripped) < _ILLUSTRATION_MAX_LEN
                and _ILLUSTRATION_CAPTION_RE.match(stripped)
            ):
                result.append(Section(
                    text=section.text,
                    segments=section.segments,
                    section_type="illustration",
                ))
                continue

            result.append(section)

        return result
