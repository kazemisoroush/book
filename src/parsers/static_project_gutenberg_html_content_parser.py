"""Static parser for Project Gutenberg HTML books.

Extracts chapters and sections from the HTML produced by Project Gutenberg.
This module is an adapter — it lives in the parsers layer and may only import
from domain and below.

Key design decisions
--------------------
* ``_extract_text_and_emphases`` walks the BS4 node tree manually rather than
  calling ``tag.get_text(strip=True)``.  The built-in helper does not insert
  a separator between inline-tag boundaries, which causes adjacent words to
  merge (e.g. ``<em>You</em>want`` → ``"Youwant"``).  The custom walker
  inserts a single space at every inline-element boundary and then collapses
  runs of whitespace to a single space.
* Emphasis tags (``<em>``, ``<b>``, ``<strong>``, ``<i>``) are recorded as
  :class:`~src.domain.models.EmphasisSpan` character-range spans relative to
  the final plain-text string.  This is a universal abstraction — the HTML
  source is merely one producer; other formats can populate the same field.
"""
from bs4 import BeautifulSoup, NavigableString, Tag
from src.parsers.book_content_parser import BookContentParser
from src.domain.models import BookContent, Chapter, Section, EmphasisSpan

_EMPHASIS_TAGS: frozenset[str] = frozenset({"em", "b", "strong", "i"})


def _extract_text_and_emphases(
    tag: Tag,
) -> tuple[str, list[EmphasisSpan]]:
    """Walk *tag*'s subtree and return (plain_text, emphasis_spans).

    The plain text is built by concatenating all NavigableString leaves.
    A single space is appended whenever the walk exits an inline element
    so that ``<em>You</em>want`` becomes ``"You want"`` rather than
    ``"Youwant"``.  Consecutive whitespace is collapsed to a single space
    and the result is stripped.

    EmphasisSpan character offsets are calculated against the *pre-collapse*
    accumulated buffer and then corrected after the final normalisation step.
    Because we build both the text and the spans together, the offsets are
    always consistent with the returned ``plain_text``.

    Args:
        tag: A BeautifulSoup Tag representing a paragraph (or any container).

    Returns:
        A two-tuple ``(plain_text, spans)`` where ``spans`` is a list of
        :class:`EmphasisSpan` objects whose ``start``/``end`` are character
        offsets into ``plain_text``.
    """
    parts: list[str] = []
    raw_spans: list[tuple[int, int, str]] = []  # (raw_start, raw_end, kind)

    def _walk(node: Tag | NavigableString, emphasis_kind: str | None) -> None:
        if isinstance(node, NavigableString):
            parts.append(str(node))
        elif isinstance(node, Tag):
            tag_name = node.name.lower() if node.name else ""
            is_emphasis = tag_name in _EMPHASIS_TAGS
            # If this tag introduces a new emphasis kind, record the span
            active_kind = emphasis_kind if emphasis_kind else None
            if is_emphasis:
                active_kind = tag_name
                span_start = sum(len(p) for p in parts)

            for child in node.children:
                _walk(child, active_kind)  # type: ignore[arg-type]

            if is_emphasis:
                span_end = sum(len(p) for p in parts)
                raw_spans.append((span_start, span_end, tag_name))
                # Insert a boundary space so adjacent text doesn't merge.
                # We only add it if there isn't already trailing whitespace in
                # the accumulated buffer.
                current = "".join(parts)
                if current and not current[-1].isspace():
                    parts.append(" ")

    _walk(tag, None)

    raw_text = "".join(parts)

    # Build a mapping from raw offsets to collapsed offsets.
    # We collapse runs of whitespace to a single space and strip edges.
    # Strategy: iterate raw_text character by character; track the output
    # position as we skip/collapse whitespace.
    collapsed_chars: list[str] = []
    raw_to_collapsed: list[int] = []  # raw_to_collapsed[i] = position in collapsed text
    prev_was_space = False
    for raw_idx, ch in enumerate(raw_text):
        if ch.isspace():
            if not prev_was_space and collapsed_chars:
                collapsed_chars.append(" ")
                raw_to_collapsed.append(len(collapsed_chars) - 1)
            else:
                # Leading space or consecutive space: skip but map to current pos
                raw_to_collapsed.append(len(collapsed_chars))
            prev_was_space = True
        else:
            collapsed_chars.append(ch)
            raw_to_collapsed.append(len(collapsed_chars) - 1)
            prev_was_space = False

    plain_text = "".join(collapsed_chars).strip()
    # Compute how many chars the leading whitespace occupies in collapsed_str,
    # so that span offsets can be adjusted after the strip() call.
    collapsed_str = "".join(collapsed_chars)
    left_offset = len(collapsed_str) - len(collapsed_str.lstrip())

    def _collapsed_pos(raw_pos: int) -> int:
        """Convert a raw character position to a collapsed+stripped offset."""
        if raw_pos >= len(raw_to_collapsed):
            # Position is past end of raw text (e.g. a boundary space we appended)
            collapsed_pos = len(collapsed_chars)
        else:
            collapsed_pos = raw_to_collapsed[raw_pos]
        # Adjust for left-strip
        adjusted = collapsed_pos - left_offset
        return max(0, adjusted)

    spans: list[EmphasisSpan] = []
    for raw_start, raw_end, kind in raw_spans:
        c_start = _collapsed_pos(raw_start)
        # raw_end points to one past the last char of the emphasis text
        # (before the boundary space we may have injected).  Map it carefully.
        if raw_end > 0 and raw_end <= len(raw_to_collapsed):
            # The last char of the emphasis content is at raw_end - 1
            c_end = raw_to_collapsed[raw_end - 1] + 1 - left_offset
        else:
            c_end = _collapsed_pos(raw_end)
        c_start = max(0, c_start)
        c_end = max(c_start, c_end)
        # Only include spans that have non-zero width and are within bounds
        if c_start < c_end and c_start < len(plain_text):
            spans.append(EmphasisSpan(start=c_start, end=c_end, kind=kind))

    return plain_text, spans


class StaticProjectGutenbergHTMLContentParser(BookContentParser):
    """Parses Project Gutenberg HTML into a BookContent with emphasis spans."""

    def parse(self, content: str) -> BookContent:
        soup = BeautifulSoup(content, 'html.parser')
        chapters = []
        chapter_number = 0

        chapter_headings = soup.find_all('h2')

        for i, heading in enumerate(chapter_headings):
            heading_text = heading.get_text(strip=True)
            if 'CHAPTER' in heading_text.upper():
                chapter_number += 1
                next_heading = (
                    chapter_headings[i + 1]
                    if i + 1 < len(chapter_headings)
                    else None
                )
                sections = self._extract_sections(heading, next_heading)
                chapters.append(Chapter(
                    number=chapter_number,
                    title=heading_text,
                    sections=sections,
                ))

        return BookContent(chapters=chapters)

    def _extract_sections(
        self,
        start_heading: Tag,
        end_heading: Tag | None,
    ) -> list[Section]:
        sections: list[Section] = []
        current: Tag | None = start_heading

        while current is not None:
            current = current.find_next()  # type: ignore[assignment]
            if current == end_heading:
                break
            if current is not None and current.name == 'p':
                text, emphases = _extract_text_and_emphases(current)
                if text:
                    sections.append(Section(text=text, emphases=emphases))

        return sections
