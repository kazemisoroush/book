"""Tests for StaticProjectGutenbergHTMLContentParser."""
import unittest
from src.parsers.static_project_gutenberg_html_content_parser import (
    StaticProjectGutenbergHTMLContentParser,
)
from src.domain.models import EmphasisSpan, Section


class TestStaticProjectGutenbergHTMLContentParser(unittest.TestCase):

    def test_parse_extracts_single_chapter(self):
        html_content = '''
        <html>
        <body>
            <h2>CHAPTER I.</h2>
            <p>First paragraph.</p>
        </body>
        </html>
        '''
        parser = StaticProjectGutenbergHTMLContentParser()
        result = parser.parse(html_content)

        self.assertEqual(len(result.chapters), 1)
        self.assertEqual(result.chapters[0].number, 1)
        self.assertEqual(result.chapters[0].title, "CHAPTER I.")

    def test_parse_extracts_chapter_sections(self):
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
        result = parser.parse(html_content)

        self.assertEqual(len(result.chapters[0].sections), 2)
        self.assertEqual(result.chapters[0].sections[0].text, "First paragraph.")
        self.assertEqual(result.chapters[0].sections[1].text, "Second paragraph.")

    def test_parse_extracts_multiple_chapters(self):
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
        result = parser.parse(html_content)

        self.assertEqual(len(result.chapters), 2)
        self.assertEqual(result.chapters[0].number, 1)
        self.assertEqual(result.chapters[1].number, 2)

    def test_parse_handles_chapter_with_title(self):
        html_content = '''
        <html>
        <body>
            <h2>CHAPTER I. The Beginning</h2>
            <p>Chapter content.</p>
        </body>
        </html>
        '''
        parser = StaticProjectGutenbergHTMLContentParser()
        result = parser.parse(html_content)

        self.assertEqual(result.chapters[0].title, "CHAPTER I. The Beginning")

    def test_parse_skips_empty_paragraphs(self):
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
        result = parser.parse(html_content)

        self.assertEqual(len(result.chapters[0].sections), 2)

    def test_parse_returns_empty_chapters_for_no_content(self):
        html_content = '<html><body></body></html>'
        parser = StaticProjectGutenbergHTMLContentParser()
        result = parser.parse(html_content)

        self.assertEqual(len(result.chapters), 0)

    def test_parse_extracts_sections_when_h2_wrapped_in_div(self):
        # Real Project Gutenberg structure with divs
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
        result = parser.parse(html_content)

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
    section = _parse_first_section("<p><em>You</em>want to go?</p>")
    assert section.text == "You want to go?"


def test_word_merge_bug_b_tag_inserts_space() -> None:
    """<b>word</b>next must not merge words."""
    section = _parse_first_section("<p><b>word</b>next</p>")
    assert section.text == "word next"


def test_word_merge_no_double_space_when_trailing_space_in_tag() -> None:
    """<em>Hello </em>world must not produce double space."""
    section = _parse_first_section("<p><em>Hello </em>world</p>")
    assert section.text == "Hello world"


def test_word_merge_no_double_space_when_leading_space_outside_tag() -> None:
    """word<em> there</em> must produce 'word there' not 'word  there'."""
    section = _parse_first_section("<p>word<em> there</em></p>")
    assert section.text == "word there"


def test_plain_paragraph_text_unchanged() -> None:
    """Plain paragraph text (no inline tags) is preserved exactly."""
    section = _parse_first_section("<p>It was a dark and stormy night.</p>")
    assert section.text == "It was a dark and stormy night."


# ── Emphasis extraction ───────────────────────────────────────────────────────

def test_em_tag_produces_emphasis_span() -> None:
    """<em>You</em> at position 0 produces EmphasisSpan(0, 3, 'em')."""
    section = _parse_first_section("<p><em>You</em> want to go?</p>")
    assert len(section.emphases) == 1
    span = section.emphases[0]
    assert span.start == 0
    assert span.end == 3
    assert span.kind == "em"


def test_b_tag_produces_emphasis_span_with_kind_b() -> None:
    """<b> tag produces EmphasisSpan with kind='b'."""
    section = _parse_first_section("<p>Say <b>hello</b> now.</p>")
    assert len(section.emphases) == 1
    assert section.emphases[0].kind == "b"


def test_strong_tag_produces_emphasis_span_with_kind_strong() -> None:
    """<strong> tag produces EmphasisSpan with kind='strong'."""
    section = _parse_first_section("<p>This is <strong>important</strong>.</p>")
    assert len(section.emphases) == 1
    assert section.emphases[0].kind == "strong"


def test_i_tag_produces_emphasis_span_with_kind_i() -> None:
    """<i> tag produces EmphasisSpan with kind='i'."""
    section = _parse_first_section("<p>The ship <i>Mary Rose</i> sank.</p>")
    assert len(section.emphases) == 1
    assert section.emphases[0].kind == "i"


def test_emphasis_span_offsets_correct_mid_sentence() -> None:
    """EmphasisSpan offsets point to the right characters in text."""
    # "Say hello now." — "hello" starts at 4, ends at 9
    section = _parse_first_section("<p>Say <b>hello</b> now.</p>")
    span = section.emphases[0]
    assert section.text[span.start:span.end] == "hello"


def test_multiple_emphasis_spans_all_captured() -> None:
    """Two emphasis tags in one paragraph produce two spans."""
    section = _parse_first_section(
        "<p><em>First</em> and <em>second</em>.</p>"
    )
    assert len(section.emphases) == 2


def test_multiple_spans_offsets_are_correct() -> None:
    """Both span offsets in a two-emphasis paragraph are correct."""
    section = _parse_first_section(
        "<p><em>First</em> and <em>second</em>.</p>"
    )
    text = section.text
    span1, span2 = section.emphases[0], section.emphases[1]
    assert text[span1.start:span1.end] == "First"
    assert text[span2.start:span2.end] == "second"


def test_plain_paragraph_has_empty_emphases() -> None:
    """A paragraph without any inline emphasis tags has emphases=[]."""
    section = _parse_first_section("<p>No emphasis here.</p>")
    assert section.emphases == []


def test_emphasis_span_is_emphasis_span_instance() -> None:
    """The objects in emphases are EmphasisSpan instances."""
    section = _parse_first_section("<p><em>word</em> follows.</p>")
    assert isinstance(section.emphases[0], EmphasisSpan)


if __name__ == '__main__':
    unittest.main()
