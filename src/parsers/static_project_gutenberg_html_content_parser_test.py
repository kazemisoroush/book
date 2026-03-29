"""Tests for StaticProjectGutenbergHTMLContentParser."""
import unittest
from src.parsers.static_project_gutenberg_html_content_parser import (
    StaticProjectGutenbergHTMLContentParser,
)
from src.domain.models import EmphasisSpan, Section


class TestStaticProjectGutenbergHTMLContentParser(unittest.TestCase):

    def test_parse_extracts_single_chapter(self):
        # Arrange
        html_content = '''
        <html>
        <body>
            <h2>CHAPTER I.</h2>
            <p>First paragraph.</p>
        </body>
        </html>
        '''
        parser = StaticProjectGutenbergHTMLContentParser()

        # Act
        result = parser.parse(html_content)

        # Assert
        self.assertEqual(len(result.chapters), 1)
        self.assertEqual(result.chapters[0].number, 1)
        self.assertEqual(result.chapters[0].title, "CHAPTER I.")

    def test_parse_extracts_chapter_sections(self):
        # Arrange
        html_content = '''
        <html>
        <body>
            <h2>CHAPTER I.</h2>
            <p>First paragraph.</p>
            <p>Second paragraph.</p>
        </body>
        </html>
        '''
        parser = StaticProjectGutenbergHTMLContentParser()

        # Act
        result = parser.parse(html_content)

        # Assert
        self.assertEqual(len(result.chapters[0].sections), 2)
        self.assertEqual(result.chapters[0].sections[0].text, "First paragraph.")
        self.assertEqual(result.chapters[0].sections[1].text, "Second paragraph.")

    def test_parse_extracts_multiple_chapters(self):
        # Arrange
        html_content = '''
        <html>
        <body>
            <h2>CHAPTER I.</h2>
            <p>First chapter content.</p>
            <h2>CHAPTER II.</h2>
            <p>Second chapter content.</p>
        </body>
        </html>
        '''
        parser = StaticProjectGutenbergHTMLContentParser()

        # Act
        result = parser.parse(html_content)

        # Assert
        self.assertEqual(len(result.chapters), 2)
        self.assertEqual(result.chapters[0].number, 1)
        self.assertEqual(result.chapters[1].number, 2)

    def test_parse_handles_chapter_with_title(self):
        # Arrange
        html_content = '''
        <html>
        <body>
            <h2>CHAPTER I. The Beginning</h2>
            <p>Chapter content.</p>
        </body>
        </html>
        '''
        parser = StaticProjectGutenbergHTMLContentParser()

        # Act
        result = parser.parse(html_content)

        # Assert
        self.assertEqual(result.chapters[0].title, "CHAPTER I. The Beginning")

    def test_parse_skips_empty_paragraphs(self):
        # Arrange
        html_content = '''
        <html>
        <body>
            <h2>CHAPTER I.</h2>
            <p>Content.</p>
            <p></p>
            <p>More content.</p>
        </body>
        </html>
        '''
        parser = StaticProjectGutenbergHTMLContentParser()

        # Act
        result = parser.parse(html_content)

        # Assert
        self.assertEqual(len(result.chapters[0].sections), 2)

    def test_parse_returns_empty_chapters_for_no_content(self):
        # Arrange
        html_content = '<html><body></body></html>'
        parser = StaticProjectGutenbergHTMLContentParser()

        # Act
        result = parser.parse(html_content)

        # Assert
        self.assertEqual(len(result.chapters), 0)

    def test_parse_extracts_sections_when_h2_wrapped_in_div(self):
        # Arrange — real Project Gutenberg structure with divs
        html_content = '''
        <html>
        <body>
            <div class='chapter'><h2>CHAPTER I</h2></div>
            <p>First paragraph.</p>
            <p>Second paragraph.</p>
            <div class='chapter'><h2>CHAPTER II</h2></div>
            <p>Third paragraph.</p>
        </body>
        </html>
        '''
        parser = StaticProjectGutenbergHTMLContentParser()

        # Act
        result = parser.parse(html_content)

        # Assert
        self.assertEqual(len(result.chapters), 2)
        self.assertEqual(len(result.chapters[0].sections), 2)
        self.assertEqual(result.chapters[0].sections[0].text, "First paragraph.")  # noqa: E501
        self.assertEqual(result.chapters[0].sections[1].text, "Second paragraph.")  # noqa: E501
        self.assertEqual(len(result.chapters[1].sections), 1)
        self.assertEqual(result.chapters[1].sections[0].text, "Third paragraph.")  # noqa: E501


# ── Word-merge bug fix ────────────────────────────────────────────────────────

def _parse_first_section(html_para: str) -> Section:
    """Helper: wrap a single <p> in a minimal chapter HTML and parse it."""
    html = f"""
    <html><body>
        <h2>CHAPTER I.</h2>
        {html_para}
    </body></html>
    """
    parser = StaticProjectGutenbergHTMLContentParser()
    result = parser.parse(html)
    return result.chapters[0].sections[0]


def test_word_merge_bug_em_tag_inserts_space() -> None:
    """<em>You</em>want must produce 'You want', not 'Youwant'."""
    # Act
    section = _parse_first_section("<p><em>You</em>want to go?</p>")

    # Assert
    assert section.text == "You want to go?"


def test_word_merge_bug_b_tag_inserts_space() -> None:
    """<b>word</b>next must not merge words."""
    # Act
    section = _parse_first_section("<p><b>word</b>next</p>")

    # Assert
    assert section.text == "word next"


def test_word_merge_no_double_space_when_trailing_space_in_tag() -> None:
    """<em>Hello </em>world must not produce double space."""
    # Act
    section = _parse_first_section("<p><em>Hello </em>world</p>")

    # Assert
    assert section.text == "Hello world"


def test_word_merge_no_double_space_when_leading_space_outside_tag() -> None:
    """word<em> there</em> must produce 'word there' not 'word  there'."""
    # Act
    section = _parse_first_section("<p>word<em> there</em></p>")

    # Assert
    assert section.text == "word there"


def test_plain_paragraph_text_unchanged() -> None:
    """Plain paragraph text (no inline tags) is preserved exactly."""
    # Act
    section = _parse_first_section("<p>It was a dark and stormy night.</p>")

    # Assert
    assert section.text == "It was a dark and stormy night."


# ── Emphasis extraction ───────────────────────────────────────────────────────

def test_em_tag_produces_emphasis_span() -> None:
    """<em>You</em> at position 0 produces EmphasisSpan(0, 3, 'em')."""
    # Act
    section = _parse_first_section("<p><em>You</em> want to go?</p>")

    # Assert
    assert len(section.emphases) == 1
    span = section.emphases[0]
    assert span.start == 0
    assert span.end == 3
    assert span.kind == "em"


def test_b_tag_produces_emphasis_span_with_kind_b() -> None:
    """<b> tag produces EmphasisSpan with kind='b'."""
    # Act
    section = _parse_first_section("<p>Say <b>hello</b> now.</p>")

    # Assert
    assert len(section.emphases) == 1
    assert section.emphases[0].kind == "b"


def test_strong_tag_produces_emphasis_span_with_kind_strong() -> None:
    """<strong> tag produces EmphasisSpan with kind='strong'."""
    # Act
    section = _parse_first_section("<p>This is <strong>important</strong>.</p>")

    # Assert
    assert len(section.emphases) == 1
    assert section.emphases[0].kind == "strong"


def test_i_tag_produces_emphasis_span_with_kind_i() -> None:
    """<i> tag produces EmphasisSpan with kind='i'."""
    # Act
    section = _parse_first_section("<p>The ship <i>Mary Rose</i> sank.</p>")

    # Assert
    assert len(section.emphases) == 1
    assert section.emphases[0].kind == "i"


def test_emphasis_span_offsets_correct_mid_sentence() -> None:
    """EmphasisSpan offsets point to the right characters in text."""
    # Act — "Say hello now." — "hello" starts at 4, ends at 9
    section = _parse_first_section("<p>Say <b>hello</b> now.</p>")

    # Assert
    span = section.emphases[0]
    assert section.text[span.start:span.end] == "hello"


def test_multiple_emphasis_spans_all_captured() -> None:
    """Two emphasis tags in one paragraph produce two spans."""
    # Act
    section = _parse_first_section(
        "<p><em>First</em> and <em>second</em>.</p>"
    )

    # Assert
    assert len(section.emphases) == 2


def test_multiple_spans_offsets_are_correct() -> None:
    """Both span offsets in a two-emphasis paragraph are correct."""
    # Act
    section = _parse_first_section(
        "<p><em>First</em> and <em>second</em>.</p>"
    )

    # Assert
    text = section.text
    span1, span2 = section.emphases[0], section.emphases[1]
    assert text[span1.start:span1.end] == "First"
    assert text[span2.start:span2.end] == "second"


def test_plain_paragraph_has_empty_emphases() -> None:
    """A paragraph without any inline emphasis tags has emphases=[]."""
    # Act
    section = _parse_first_section("<p>No emphasis here.</p>")

    # Assert
    assert section.emphases == []


def test_emphasis_span_is_emphasis_span_instance() -> None:
    """The objects in emphases are EmphasisSpan instances."""
    # Act
    section = _parse_first_section("<p><em>word</em> follows.</p>")

    # Assert
    assert isinstance(section.emphases[0], EmphasisSpan)


# ── Chapter title bleed fix (US-004) ─────────────────────────────────────────


def test_chapter_title_excludes_span_caption_text() -> None:
    """A <span class="caption"> inside an <h2> must not appear in the title.

    Mirrors the real Gutenberg structure where chapter headings contain an
    inline image + caption span followed by the actual chapter text node.
    The caption is an image description, NOT part of the heading.
    """
    # Arrange
    html = """
    <html><body>
        <h2>
            <a id="CHAPTER_II"></a>
            <img alt="" src="images/foo.jpg">
            <span class="caption">I hope Mr. Bingley will like it.</span>
            <br><br>CHAPTER II.
        </h2>
        <p>Some content.</p>
    </body></html>
    """
    parser = StaticProjectGutenbergHTMLContentParser()

    # Act
    result = parser.parse(html)

    # Assert
    assert len(result.chapters) == 1
    assert result.chapters[0].title == "CHAPTER II."


def test_chapter_title_without_caption_unchanged() -> None:
    """An <h2> with no caption span returns the full text node unchanged."""
    # Arrange
    html = """
    <html><body>
        <h2><a id="CHAPTER_IV"></a><img alt="" src="images/foo.jpg">
            <br><br>CHAPTER IV.</h2>
        <p>Content here.</p>
    </body></html>
    """
    parser = StaticProjectGutenbergHTMLContentParser()

    # Act
    result = parser.parse(html)

    # Assert
    assert len(result.chapters) == 1
    assert result.chapters[0].title == "CHAPTER IV."


def test_multiple_chapters_caption_bleed_excluded() -> None:
    """Multi-chapter parse: caption text never bleeds into chapter titles.

    Reproduces the Pride and Prejudice bug where chapters 2 and 3 gained
    leading sentence fragments from image captions.
    """
    # Arrange
    html = """
    <html><body>
        <h2><a id="Chapter_I"></a>
            Chapter I.</h2>
        <p>First chapter content.</p>

        <h2>
            <a id="CHAPTER_II"></a>
            <img alt="" src="images/ch2.jpg">
            <span class="caption">I hope Mr. Bingley will like it.</span>
            <br><br>CHAPTER II.
        </h2>
        <p>Second chapter content.</p>

        <h2>
            <a id="CHAPTER_III"></a>
            <img alt="" src="images/ch3.jpg">
            <span class="caption">He rode a black horse.</span>
            <br><br>CHAPTER III.
        </h2>
        <p>Third chapter content.</p>
    </body></html>
    """
    parser = StaticProjectGutenbergHTMLContentParser()

    # Act
    result = parser.parse(html)

    # Assert
    assert len(result.chapters) == 3
    assert result.chapters[0].title == "Chapter I."
    assert result.chapters[1].title == "CHAPTER II."
    assert result.chapters[2].title == "CHAPTER III."


def test_pride_and_prejudice_chapter_titles_match_pattern() -> None:
    """All chapter titles in Pride and Prejudice (book 1342) contain only
    heading text and no caption bleed.

    Acceptance criterion #2 from US-004: titles should start with a
    case-insensitive variant of "CHAPTER" and contain no sentence-ending
    punctuation followed by more text (which would indicate caption bleed).

    Note: some headings in the source HTML have no space between "CHAPTER"
    and the Roman numeral (e.g. "CHAPTERXXVII.") — this is a source data
    quirk, not a parser bug.  The check here is specifically that captions
    (e.g. "I hope Mr. Bingley will like it.") do NOT appear in any title.
    """
    import re
    import os

    # Arrange
    book_path = "/workspaces/book/books/1342/pg1342-images.html"
    if not os.path.exists(book_path):
        return  # Skip when fixture not present

    with open(book_path, encoding="utf-8") as f:
        html = f.read()

    parser = StaticProjectGutenbergHTMLContentParser()

    # Act
    result = parser.parse(html)

    # Assert
    assert len(result.chapters) > 0, "Expected chapters to be parsed"

    heading_start = re.compile(r'^[Cc][Hh][Aa][Pp][Tt][Ee][Rr]')
    caption_bleed = re.compile(r'\.\s*[A-Z].*CHAPTER', re.IGNORECASE)

    for chapter in result.chapters:
        title = chapter.title.strip()
        assert heading_start.match(title), (
            f"Chapter {chapter.number} title does not start with 'CHAPTER'. "
            f"Got: {repr(title)}"
        )
        assert not caption_bleed.search(title), (
            f"Chapter {chapter.number} title contains caption bleed. "
            f"Got: {repr(title)}"
        )


if __name__ == '__main__':
    unittest.main()


# ── SectionFilter integration (US-007) ───────────────────────────────────────


def test_parser_drops_page_number_artifact_sections() -> None:
    """Page number artifact paragraphs (e.g. '{6}') are removed from parsed output."""
    # Arrange
    html = """
    <html><body>
        <h2>CHAPTER I.</h2>
        <p>Normal prose paragraph.</p>
        <p>{6}</p>
        <p>Another normal paragraph.</p>
    </body></html>
    """
    parser = StaticProjectGutenbergHTMLContentParser()

    # Act
    result = parser.parse(html)

    # Assert
    texts = [s.text for s in result.chapters[0].sections]
    assert "{6}" not in texts
    assert "Normal prose paragraph." in texts
    assert "Another normal paragraph." in texts


def test_parser_drops_multiple_page_number_artifacts() -> None:
    """Multiple page number artifacts are all removed."""
    # Arrange
    html = """
    <html><body>
        <h2>CHAPTER I.</h2>
        <p>{1}</p>
        <p>Prose.</p>
        <p>{2}</p>
    </body></html>
    """
    parser = StaticProjectGutenbergHTMLContentParser()

    # Act
    result = parser.parse(html)

    # Assert
    sections = result.chapters[0].sections
    assert len(sections) == 1
    assert sections[0].text == "Prose."


def test_parser_drops_copyright_block_sections() -> None:
    """In-page copyright blocks ('[Copyright ...]') are removed from parsed output."""
    # Arrange
    html = """
    <html><body>
        <h2>CHAPTER I.</h2>
        <p>Prose before.</p>
        <p>[Copyright 1894 by George Allen. ]</p>
        <p>Prose after.</p>
    </body></html>
    """
    parser = StaticProjectGutenbergHTMLContentParser()

    # Act
    result = parser.parse(html)

    # Assert
    texts = [s.text for s in result.chapters[0].sections]
    assert "[Copyright 1894 by George Allen. ]" not in texts
    assert "Prose before." in texts
    assert "Prose after." in texts


def test_parser_keeps_illustration_caption_with_type_tagged() -> None:
    """'Mr. & Mrs. Bennet' caption paragraph is kept and tagged section_type='illustration'."""
    # Arrange
    html = """
    <html><body>
        <h2>CHAPTER I.</h2>
        <p>Normal prose.</p>
        <p>Mr. & Mrs. Bennet</p>
    </body></html>
    """
    parser = StaticProjectGutenbergHTMLContentParser()

    # Act
    result = parser.parse(html)

    # Assert
    sections = result.chapters[0].sections
    illustration_sections = [s for s in sections if s.section_type == "illustration"]
    assert len(illustration_sections) == 1
    assert illustration_sections[0].text == "Mr. & Mrs. Bennet"


def test_parser_illustration_caption_not_discarded() -> None:
    """Illustration captions appear in the sections list (not dropped like page numbers)."""
    # Arrange
    html = """
    <html><body>
        <h2>CHAPTER I.</h2>
        <p>Normal prose.</p>
        <p>Mr. & Mrs. Bennet</p>
    </body></html>
    """
    parser = StaticProjectGutenbergHTMLContentParser()

    # Act
    result = parser.parse(html)

    # Assert — 2 sections: prose + illustration
    assert len(result.chapters[0].sections) == 2


def test_parser_normal_prose_sections_have_no_section_type() -> None:
    """Normal prose sections parsed by the HTML parser have section_type=None."""
    # Arrange
    html = """
    <html><body>
        <h2>CHAPTER I.</h2>
        <p>It is a truth universally acknowledged.</p>
    </body></html>
    """
    parser = StaticProjectGutenbergHTMLContentParser()

    # Act
    result = parser.parse(html)

    # Assert
    sections = result.chapters[0].sections
    assert len(sections) == 1
    assert sections[0].section_type is None
