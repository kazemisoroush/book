import glob
from src.parsers.book_metadata_parser import BookMetadataParser
from src.parsers.book_content_parser import BookContentParser
from src.domain.models import Book


class ParseCommand:

    def __init__(self, metadata_parser: BookMetadataParser, content_parser: BookContentParser):
        self._metadata_parser = metadata_parser
        self._content_parser = content_parser

    def execute(self, book_id: int) -> Book:
        html_files = glob.glob(f"books/{book_id}/*.html")
        if not html_files:
            return None

        with open(html_files[0], 'r', encoding='utf-8') as f:
            content = f.read()

        metadata = self._metadata_parser.parse(content)
        book_content = self._content_parser.parse(content)

        return Book(metadata=metadata, content=book_content)
