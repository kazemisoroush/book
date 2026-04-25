"""Tests for StaticProjectGutenbergHTMLContentParser."""
import unittest

from src.domain.models import Section
from src.parsers.static_project_gutenberg_html_content_parser import (
    StaticProjectGutenbergHTMLContentParser,
)


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
    """<em>You</em>want must produce 'YOU want', not 'YOUwant'."""
    # Arrange — input HTML is inline; helper creates parser and chapter wrapper

    # Act
    section = _parse_first_section("<p><em>You</em>want to go?</p>")

    # Assert — emphasis uppercased, boundary space still inserted
    assert section.text == "YOU want to go?"


def test_word_merge_bug_b_tag_inserts_space() -> None:
    """<b>word</b>next must not merge words; emphasis content is uppercased."""
    # Arrange — input HTML is inline; helper creates parser and chapter wrapper

    # Act
    section = _parse_first_section("<p><b>word</b>next</p>")

    # Assert
    assert section.text == "WORD next"


def test_word_merge_no_double_space_when_trailing_space_in_tag() -> None:
    """<em>Hello </em>world must not produce double space; emphasis uppercased."""
    # Arrange — input HTML is inline; helper creates parser and chapter wrapper

    # Act
    section = _parse_first_section("<p><em>Hello </em>world</p>")

    # Assert
    assert section.text == "HELLO world"


def test_word_merge_no_double_space_when_leading_space_outside_tag() -> None:
    """word<em> there</em> must produce 'word THERE' not 'word  THERE'."""
    # Arrange — input HTML is inline; helper creates parser and chapter wrapper

    # Act
    section = _parse_first_section("<p>word<em> there</em></p>")

    # Assert
    assert section.text == "word THERE"


def test_plain_paragraph_text_unchanged() -> None:
    """Plain paragraph text (no inline tags) is preserved exactly."""
    # Arrange — input HTML is inline; helper creates parser and chapter wrapper

    # Act
    section = _parse_first_section("<p>It was a dark and stormy night.</p>")

    # Assert
    assert section.text == "It was a dark and stormy night."


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
    import os
    import re

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


# ── US-009: Emphasis → ALL-CAPS ───────────────────────────────────────────────


def test_em_tag_content_is_uppercased() -> None:
    """<em>word</em> must produce the word in ALL-CAPS in section.text."""
    # Arrange — input HTML is inline; helper creates parser and chapter wrapper

    # Act
    section = _parse_first_section("<p>She said <em>never</em> again.</p>")

    # Assert
    assert "NEVER" in section.text
    assert "never" not in section.text.replace("NEVER", "")


def test_b_tag_content_is_uppercased() -> None:
    """<b>word</b> must produce the word in ALL-CAPS in section.text."""
    # Arrange — input HTML is inline; helper creates parser and chapter wrapper

    # Act
    section = _parse_first_section("<p>Do <b>not</b> enter.</p>")

    # Assert
    assert "NOT" in section.text


def test_strong_tag_content_is_uppercased() -> None:
    """<strong>word</strong> must produce the word in ALL-CAPS in section.text."""
    # Arrange — input HTML is inline; helper creates parser and chapter wrapper

    # Act
    section = _parse_first_section("<p>This is <strong>important</strong>.</p>")

    # Assert
    assert "IMPORTANT" in section.text


def test_i_tag_content_is_uppercased() -> None:
    """<i>word</i> must produce the word in ALL-CAPS in section.text."""
    # Arrange — input HTML is inline; helper creates parser and chapter wrapper

    # Act
    section = _parse_first_section("<p>The ship <i>Mary Rose</i> sank.</p>")

    # Assert
    assert "MARY ROSE" in section.text


def test_multi_word_em_span_all_uppercased() -> None:
    """<em>never wanted to go</em> must produce NEVER WANTED TO GO (all words)."""
    # Arrange — input HTML is inline; helper creates parser and chapter wrapper

    # Act
    section = _parse_first_section("<p>She had <em>never wanted to go</em> there.</p>")

    # Assert
    assert "NEVER WANTED TO GO" in section.text


def test_non_emphasis_text_not_uppercased() -> None:
    """Text outside emphasis tags must remain unchanged (not uppercased)."""
    # Arrange — input HTML is inline; helper creates parser and chapter wrapper

    # Act
    section = _parse_first_section("<p>She said <em>never</em> again.</p>")

    # Assert — surrounding text is lowercase
    assert section.text.startswith("She said")
    assert section.text.endswith("again.")


# ── div.caption / div.figcenter as illustration (bug fix) ─────────────────────


def test_p_inside_div_caption_inside_figcenter_is_tagged_illustration() -> None:
    """A <p> inside <div class='caption'> inside <div class='figcenter'> must be
    tagged section_type='illustration', not treated as normal narration.

    This is the root cause of the bug where 'He came down to see the place'
    (a figure caption in Pride and Prejudice) was passed to the AI as dialogue.
    """
    # Arrange
    html = """
    <html><body>
        <h2>CHAPTER I.</h2>
        <div class="figcenter">
            <div class="caption">
                <p>"He came down to see the place"</p>
            </div>
        </div>
        <p>Normal prose.</p>
    </body></html>
    """
    parser = StaticProjectGutenbergHTMLContentParser()

    # Act
    result = parser.parse(html)

    # Assert — the caption paragraph is tagged illustration, not None
    caption_sections = [
        s for s in result.chapters[0].sections
        if "He came down" in s.text
    ]
    assert len(caption_sections) == 1
    assert caption_sections[0].section_type == "illustration"


def test_p_inside_figcenter_directly_is_tagged_illustration() -> None:
    """A <p> directly inside a <div class='figcenter'> (no inner .caption div)
    must also be tagged section_type='illustration'.
    """
    # Arrange
    html = """
    <html><body>
        <h2>CHAPTER I.</h2>
        <div class="figcenter">
            <p>Illustration text directly in figcenter.</p>
        </div>
        <p>Normal prose.</p>
    </body></html>
    """
    parser = StaticProjectGutenbergHTMLContentParser()

    # Act
    result = parser.parse(html)

    # Assert
    figcenter_sections = [
        s for s in result.chapters[0].sections
        if "Illustration text directly in figcenter" in s.text
    ]
    assert len(figcenter_sections) == 1
    assert figcenter_sections[0].section_type == "illustration"


def test_normal_p_outside_figcenter_retains_none_section_type() -> None:
    """Normal <p> elements outside figcenter/caption divs continue to have
    section_type=None after the caption fix is applied (regression guard).
    """
    # Arrange
    html = """
    <html><body>
        <h2>CHAPTER I.</h2>
        <div class="figcenter">
            <div class="caption">
                <p>"He came down to see the place"</p>
            </div>
        </div>
        <p>Normal prose.</p>
    </body></html>
    """
    parser = StaticProjectGutenbergHTMLContentParser()

    # Act
    result = parser.parse(html)

    # Assert — the normal prose paragraph has section_type=None
    normal_sections = [
        s for s in result.chapters[0].sections
        if "Normal prose" in s.text
    ]
    assert len(normal_sections) == 1
    assert normal_sections[0].section_type is None


def test_real_gutenberg_he_came_down_caption_is_illustration() -> None:
    """Reproduces the exact HTML from Pride and Prejudice (pg1342-images.html lines 979-988).

    The paragraph '"He came down to see the place"' is an illustration caption
    and must never appear as a section_type=None section that could be
    misclassified as dialogue by the AI.
    """
    # Arrange — exact structure from the Gutenberg file
    html = """
    <html><body>
        <h2>CHAPTER I.</h2>
        <div class="figcenter" style="width: 550px;" role="figure" aria-labelledby="ebm_caption0">
        <img alt="" src="images/i_031.jpg" width="550">
        <div class="caption" id="ebm_caption0">
        <p>"He came down to see the place"<br></p>
        <p>[<i>Copyright 1894 by George Allen.</i>]</p>
        </div>
        </div>
        <p>This was invitation enough.</p>
    </body></html>
    """
    parser = StaticProjectGutenbergHTMLContentParser()

    # Act
    result = parser.parse(html)

    # Assert 1: no section with section_type=None contains the caption text
    ambiguous_caption_sections = [
        s for s in result.chapters[0].sections
        if "He came down to see the place" in s.text and s.section_type is None
    ]
    assert ambiguous_caption_sections == [], (
        f"Caption text leaked into narration sections: {ambiguous_caption_sections}"
    )

    # Assert 2: the normal prose paragraph is still present and untagged
    prose_sections = [
        s for s in result.chapters[0].sections
        if "This was invitation enough" in s.text
    ]
    assert len(prose_sections) == 1
    assert prose_sections[0].section_type is None


def test_copyright_p_inside_figcenter_caption_not_narration() -> None:
    """The copyright <p> inside a figcenter caption block must not appear
    as a normal narration section (section_type=None with copyright text).

    Combined scenario: a figcenter contains a .caption div with both a
    caption <p> and a copyright <p>.  Neither should leak to the AI as prose.
    """
    # Arrange
    html = """
    <html><body>
        <h2>CHAPTER I.</h2>
        <div class="figcenter" style="width: 550px;">
            <div class="caption">
                <p>"She is tolerable"</p>
                <p>[<i>Copyright 1894 by George Allen.</i>]</p>
            </div>
        </div>
        <p>Normal prose follows.</p>
    </body></html>
    """
    parser = StaticProjectGutenbergHTMLContentParser()

    # Act
    result = parser.parse(html)

    # Assert — no section with section_type=None contains "Copyright"
    copyright_in_narration = [
        s for s in result.chapters[0].sections
        if "Copyright" in s.text and s.section_type is None
    ]
    assert copyright_in_narration == [], (
        f"Copyright text leaked into narration: {copyright_in_narration}"
    )
