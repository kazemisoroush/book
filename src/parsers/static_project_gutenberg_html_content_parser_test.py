import unittest
from src.parsers.static_project_gutenberg_html_content_parser import StaticProjectGutenbergHTMLContentParser


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


if __name__ == '__main__':
    unittest.main()
