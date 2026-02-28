import unittest
from src.parsers.static_project_gutenberg_html_metadata_parser import StaticProjectGutenbergHTMLMetadataParser


class TestStaticProjectGutenbergHTMLMetadataParser(unittest.TestCase):

    def test_parse_extracts_title(self):
        html_content = '''
        <html>
        <head>
            <meta name="dc.title" content="Pride and Prejudice">
        </head>
        </html>
        '''
        parser = StaticProjectGutenbergHTMLMetadataParser()
        result = parser.parse(html_content)

        self.assertEqual(result.title, "Pride and Prejudice")

    def test_parse_extracts_author(self):
        html_content = '''
        <html>
        <head>
            <meta name="dc.creator" content="Austen, Jane">
        </head>
        </html>
        '''
        parser = StaticProjectGutenbergHTMLMetadataParser()
        result = parser.parse(html_content)

        self.assertEqual(result.author, "Austen, Jane")

    def test_parse_extracts_language(self):
        html_content = '''
        <html>
        <head>
            <meta name="dc.language" content="en">
        </head>
        </html>
        '''
        parser = StaticProjectGutenbergHTMLMetadataParser()
        result = parser.parse(html_content)

        self.assertEqual(result.language, "en")

    def test_parse_extracts_release_date(self):
        html_content = '''
        <html>
        <head>
            <meta name="dcterms.created" content="2026-02-27">
        </head>
        </html>
        '''
        parser = StaticProjectGutenbergHTMLMetadataParser()
        result = parser.parse(html_content)

        self.assertEqual(result.releaseDate, "2026-02-27")

    def test_parse_extracts_all_metadata(self):
        html_content = '''
        <html>
        <head>
            <meta name="dc.title" content="The Anatomy of Revolution">
            <meta name="dc.creator" content="Brinton, Crane">
            <meta name="dc.language" content="en">
            <meta name="dcterms.created" content="2026-02-27">
        </head>
        </html>
        '''
        parser = StaticProjectGutenbergHTMLMetadataParser()
        result = parser.parse(html_content)

        self.assertEqual(result.title, "The Anatomy of Revolution")
        self.assertEqual(result.author, "Brinton, Crane")
        self.assertEqual(result.language, "en")
        self.assertEqual(result.releaseDate, "2026-02-27")

    def test_parse_handles_missing_fields(self):
        html_content = '''
        <html>
        <head>
            <meta name="dc.title" content="Test Book">
        </head>
        </html>
        '''
        parser = StaticProjectGutenbergHTMLMetadataParser()
        result = parser.parse(html_content)

        self.assertEqual(result.title, "Test Book")
        self.assertIsNone(result.author)
        self.assertIsNone(result.language)
        self.assertIsNone(result.releaseDate)
        self.assertIsNone(result.originalPublication)
        self.assertIsNone(result.credits)


if __name__ == '__main__':
    unittest.main()
