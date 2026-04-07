"""Static parser for Project Gutenberg HTML books.

Extracts chapters and sections from the HTML produced by Project Gutenberg.
This module is an adapter — it lives in the parsers layer and may only import
from domain and below.

Key design decisions
--------------------
* ``_extract_text`` walks the BS4 node tree manually rather than calling
  ``tag.get_text(strip=True)``.  The built-in helper does not insert a
  separator between inline-tag boundaries, which causes adjacent words to
  merge (e.g. ``<em>You</em>want`` → ``"Youwant"``).  The custom walker
  inserts a single space at every inline-element boundary, collapses runs of
  whitespace to a single space, and uppercases text inside emphasis tags
  (``<em>``, ``<b>``, ``<strong>``, ``<i>``) so that the eleven_v3 TTS model
  stresses those words automatically.
* ``_extract_heading_text`` extracts chapter title text from ``<h2>`` nodes
  without including the content of ``<span class="caption">`` child elements.
  In the Project Gutenberg images edition, chapter headings embed illustration
  captions inside the ``<h2>`` tag.  Using ``tag.get_text()`` naively would
  include those captions in the chapter title (e.g. producing
  ``"I hope Mr. Bingley will like it.CHAPTER II."`` instead of
  ``"CHAPTER II."``).
* ``_extract_sections`` detects ``<p>`` elements that are descendants of
  ``<div class="figcenter">`` or ``<div class="caption">`` and tags them
  ``section_type='illustration'`` at parse time (before :class:`SectionFilter`
  runs).  This prevents illustration captions such as
  ``"He came down to see the place"`` (Project Gutenberg images edition) from
  reaching the AI section parser as ambiguous quoted text.
* :class:`SectionFilter` is applied after section extraction.  It
  removes page number artifacts (``{6}``) and in-page copyright blocks
  (``[Copyright ...]``), and tags remaining illustration captions with
  ``section_type='illustration'`` so that the AI parser can skip them.
"""
import re
from bs4 import BeautifulSoup, NavigableString, Tag
from src.parsers.book_content_parser import BookContentParser
from src.parsers.section_filter import SectionFilter
from src.domain.models import BookContent, Chapter, Section

_EMPHASIS_TAGS: frozenset[str] = frozenset({"em", "b", "strong", "i"})
# Tags whose ``class`` attribute contains this value are illustration captions
# that must not contribute to chapter heading text.
_CAPTION_CLASS: str = "caption"
# ``<div>`` class values that mark illustration containers.  Any ``<p>``
# that is a descendant of one of these divs is an illustration caption,
# not prose.
_ILLUSTRATION_DIV_CLASSES: frozenset[str] = frozenset({"figcenter", "caption"})


def _is_inside_illustration_block(tag: Tag) -> bool:
    """Return True if *tag* is a descendant of an illustration container div.

    Illustration containers are ``<div class="figcenter">`` and
    ``<div class="caption">`` elements.  Any ``<p>`` found inside one of
    these divs is an illustration caption and must be tagged
    ``section_type='illustration'`` rather than treated as prose.

    Args:
        tag: The BeautifulSoup Tag to inspect (typically a ``<p>``).

    Returns:
        ``True`` if any ancestor ``<div>`` has a class from
        :data:`_ILLUSTRATION_DIV_CLASSES`, ``False`` otherwise.
    """
    parent = tag.parent
    while parent is not None and parent.name is not None:
        if parent.name == "div":
            classes: list[str] = parent.get("class") or []  # type: ignore[assignment]
            if _ILLUSTRATION_DIV_CLASSES.intersection(classes):
                return True
        parent = parent.parent  # type: ignore[assignment]
    return False


def _extract_text(tag: Tag) -> str:
    """Walk *tag*'s subtree and return plain text with emphasis uppercased.

    The plain text is built by concatenating all NavigableString leaves.
    Text inside emphasis tags (``<em>``, ``<b>``, ``<strong>``, ``<i>``) is
    uppercased inline so that the eleven_v3 TTS model stresses those words
    automatically.

    A single space is appended whenever the walk exits an inline emphasis
    element so that ``<em>You</em>want`` becomes ``"YOU want"`` rather than
    ``"YOUwant"``.  Consecutive whitespace is collapsed to a single space
    and the result is stripped.

    Args:
        tag: A BeautifulSoup Tag representing a paragraph (or any container).

    Returns:
        The plain text string with emphasised words uppercased.
    """
    parts: list[str] = []

    def _walk(node: Tag | NavigableString, in_emphasis: bool) -> None:
        if isinstance(node, NavigableString):
            text = str(node)
            parts.append(text.upper() if in_emphasis else text)
        elif isinstance(node, Tag):
            tag_name = node.name.lower() if node.name else ""
            is_emphasis = tag_name in _EMPHASIS_TAGS
            for child in node.children:
                _walk(child, in_emphasis or is_emphasis)  # type: ignore[arg-type]
            if is_emphasis:
                current = "".join(parts)
                if current and not current[-1].isspace():
                    parts.append(" ")

    _walk(tag, False)
    return re.sub(r'\s+', ' ', "".join(parts)).strip()


def _extract_heading_text(heading: Tag) -> str:
    """Extract only the heading text from an ``<h2>`` tag.

    Project Gutenberg HTML sometimes wraps an illustration caption inside a
    ``<span class="caption">`` child of the ``<h2>``.  That caption text is an
    image description — not part of the chapter title — but
    ``tag.get_text(strip=True)`` would naively concatenate it with the real
    heading, producing e.g. ``"I hope Mr. Bingley will like it.CHAPTER II."``.

    This function collects only the NavigableString nodes that are *direct*
    children of the heading (or whose parent is not a caption-like tag),
    deliberately skipping any ``<span class="caption">`` subtrees.

    Args:
        heading: The ``<h2>`` BeautifulSoup Tag to extract text from.

    Returns:
        The plain heading text, stripped of leading/trailing whitespace and
        with internal runs of whitespace collapsed to a single space.
    """
    parts: list[str] = []
    for child in heading.children:
        if isinstance(child, NavigableString):
            parts.append(str(child))
        elif isinstance(child, Tag):
            # Skip any tag whose class list contains "caption" — these are
            # illustration descriptions, not part of the chapter heading.
            classes: list[str] = child.get("class") or []  # type: ignore[assignment]
            if _CAPTION_CLASS in classes:
                continue
            # For other inline tags (e.g. <a>, <img>, <br>) include their
            # direct NavigableString children (anchors may have no text;
            # images produce no text; <br> produces no text — all harmless).
            for grandchild in child.children:
                if isinstance(grandchild, NavigableString):
                    parts.append(str(grandchild))

    raw = "".join(parts)
    # Collapse runs of whitespace (including newlines) to a single space.
    return re.sub(r'\s+', ' ', raw).strip()


class StaticProjectGutenbergHTMLContentParser(BookContentParser):
    """Parses Project Gutenberg HTML into a BookContent."""

    def __init__(self) -> None:
        self._section_filter = SectionFilter()

    def parse(self, content: str) -> BookContent:
        """Parse content structure from Project Gutenberg HTML.
        
        Args:
            content: Raw HTML content from a Project Gutenberg book.
            
        Returns:
            BookContent with extracted chapters and sections.
        """
        soup = BeautifulSoup(content, 'html.parser')
        chapters = []
        chapter_number = 0

        chapter_headings = soup.find_all('h2')

        for i, heading in enumerate(chapter_headings):
            heading_text = _extract_heading_text(heading)
            if 'CHAPTER' in heading_text.upper():
                chapter_number += 1
                next_heading = (
                    chapter_headings[i + 1]
                    if i + 1 < len(chapter_headings)
                    else None
                )
                raw_sections = self._extract_sections(heading, next_heading)
                sections = self._section_filter.filter(raw_sections)
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
                text = _extract_text(current)
                if text:
                    if _is_inside_illustration_block(current):
                        sections.append(Section(
                            text=text,
                            section_type="illustration",
                        ))
                    else:
                        sections.append(Section(text=text))

        return sections
