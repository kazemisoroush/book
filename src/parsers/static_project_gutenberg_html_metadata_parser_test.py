import unittest

from src.parsers.static_project_gutenberg_html_metadata_parser import (
    StaticProjectGutenbergHTMLMetadataParser,
)


class TestStaticProjectGutenbergHTMLMetadataParser(unittest.TestCase):

    def test_parse_extracts_title(self):
        # Arrange
        html_content = '''
        <html>
        <head>
            <meta name="dc.title" content="Pride and Prejudice">
        </head>
        </html>
        '''
        parser = StaticProjectGutenbergHTMLMetadataParser()

        # Act
        result = parser.parse(html_content)

        # Assert
        self.assertEqual(result.title, "Pride and Prejudice")

    def test_parse_extracts_author(self):
        # Arrange
        html_content = '''
        <html>
        <head>
            <meta name="dc.creator" content="Austen, Jane">
        </head>
        </html>
        '''
        parser = StaticProjectGutenbergHTMLMetadataParser()

        # Act
        result = parser.parse(html_content)

        # Assert
        self.assertEqual(result.author, "Austen, Jane")

    def test_parse_extracts_language(self):
        # Arrange
        html_content = '''
        <html>
        <head>
            <meta name="dc.language" content="en">
        </head>
        </html>
        '''
        parser = StaticProjectGutenbergHTMLMetadataParser()

        # Act
        result = parser.parse(html_content)

        # Assert
        self.assertEqual(result.language, "en")

    def test_parse_extracts_release_date(self):
        # Arrange
        html_content = '''
        <html>
        <head>
            <meta name="dcterms.created" content="2026-02-27">
        </head>
        </html>
        '''
        parser = StaticProjectGutenbergHTMLMetadataParser()

        # Act
        result = parser.parse(html_content)

        # Assert
        self.assertEqual(result.releaseDate, "2026-02-27")

    def test_parse_extracts_all_metadata(self):
        # Arrange
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

        # Act
        result = parser.parse(html_content)

        # Assert
        self.assertEqual(result.title, "The Anatomy of Revolution")
        self.assertEqual(result.author, "Brinton, Crane")
        self.assertEqual(result.language, "en")
        self.assertEqual(result.releaseDate, "2026-02-27")

    def test_parse_handles_missing_fields(self):
        # Arrange
        html_content = '''
        <html>
        <head>
            <meta name="dc.title" content="Test Book">
        </head>
        </html>
        '''
        parser = StaticProjectGutenbergHTMLMetadataParser()

        # Act
        result = parser.parse(html_content)

        # Assert
        self.assertEqual(result.title, "Test Book")
        self.assertIsNone(result.author)
        self.assertIsNone(result.language)
        self.assertIsNone(result.releaseDate)
        self.assertIsNone(result.originalPublication)
        self.assertIsNone(result.credits)


class TestStaticProjectGutenbergHTMLMetadataParserDivFallback(unittest.TestCase):
    """Tests for the older PG format that uses div-based metadata instead of meta tags."""

    def test_parse_extracts_title_from_div_fallback(self):
        # Arrange
        html_content = '''
        <html><body>
        <div style='display:block'>Title: Foo Bar</div>
        </body></html>
        '''
        parser = StaticProjectGutenbergHTMLMetadataParser()

        # Act
        result = parser.parse(html_content)

        # Assert
        self.assertEqual(result.title, "Foo Bar")

    def test_parse_extracts_author_from_div_fallback(self):
        # Arrange
        html_content = '''
        <html><body>
        <div style='display:block'>Author: Some Author</div>
        </body></html>
        '''
        parser = StaticProjectGutenbergHTMLMetadataParser()

        # Act
        result = parser.parse(html_content)

        # Assert
        self.assertEqual(result.author, "Some Author")

    def test_parse_extracts_language_from_div_fallback(self):
        # Arrange
        html_content = '''
        <html><body>
        <div style='display:block'>Language: English</div>
        </body></html>
        '''
        parser = StaticProjectGutenbergHTMLMetadataParser()

        # Act
        result = parser.parse(html_content)

        # Assert
        self.assertEqual(result.language, "English")

    def test_parse_extracts_release_date_from_div_fallback(self):
        # Arrange
        html_content = '''
        <html><body>
        <div style='display:block'>Release Date: July, 1993 [eBook #74]</div>
        </body></html>
        '''
        parser = StaticProjectGutenbergHTMLMetadataParser()

        # Act
        result = parser.parse(html_content)

        # Assert
        self.assertEqual(result.releaseDate, "July, 1993 [eBook #74]")

    def test_parse_extracts_credits_from_div_fallback(self):
        # Arrange
        html_content = '''
        <html><body>
        <div style='display:block'>Produced by: David Widger</div>
        </body></html>
        '''
        parser = StaticProjectGutenbergHTMLMetadataParser()

        # Act
        result = parser.parse(html_content)

        # Assert
        self.assertEqual(result.credits, "David Widger")

    def test_parse_extracts_all_metadata_from_div_fallback(self):
        # Arrange
        html_content = """
        <html><body>
        <div style='display:block; margin-top:1em; margin-bottom:1em; margin-left:2em; text-indent:-2em'>Title: The Adventures of Tom Sawyer</div>
        <div style='display:block; margin-top:1em; margin-bottom:1em; margin-left:2em; text-indent:-2em'>Author: Mark Twain (Samuel Clemens)</div>
        <div style='display:block; margin:1em 0'>Release Date: July, 1993 [eBook #74]</div>
        <div style='display:block; margin:1em 0'>Language: English</div>
        <div style='display:block; margin-left:2em; text-indent:-2em'>Produced by: David Widger</div>
        </body></html>
        """
        parser = StaticProjectGutenbergHTMLMetadataParser()

        # Act
        result = parser.parse(html_content)

        # Assert
        self.assertEqual(result.title, "The Adventures of Tom Sawyer")
        self.assertEqual(result.author, "Mark Twain (Samuel Clemens)")
        self.assertEqual(result.releaseDate, "July, 1993 [eBook #74]")
        self.assertEqual(result.language, "English")
        self.assertEqual(result.credits, "David Widger")

    def test_parse_prefers_meta_tags_over_div_fallback(self):
        # Arrange
        html_content = '''
        <html>
        <head>
            <meta name="dc.title" content="Meta Title">
            <meta name="dc.creator" content="Meta Author">
            <meta name="dc.language" content="fr">
        </head>
        <body>
        <div>Title: Div Title</div>
        <div>Author: Div Author</div>
        <div>Language: Div Language</div>
        </body>
        </html>
        '''
        parser = StaticProjectGutenbergHTMLMetadataParser()

        # Act
        result = parser.parse(html_content)

        # Assert
        self.assertEqual(result.title, "Meta Title")
        self.assertEqual(result.author, "Meta Author")
        self.assertEqual(result.language, "fr")

    def test_parse_div_release_date_stops_at_br_tag(self):
        # Arrange
        html_content = """
        <html><body>
        <div style='display:block; margin:1em 0'>Release Date: July, 1993 [eBook #74]<br/>
[Most recently updated: August 9, 2023]</div>
        </body></html>
        """
        parser = StaticProjectGutenbergHTMLMetadataParser()

        # Act
        result = parser.parse(html_content)

        # Assert
        self.assertEqual(result.releaseDate, "July, 1993 [eBook #74]")


if __name__ == '__main__':
    unittest.main()
