import glob
from src.parsers.book_metadata_parser import BookMetadataParser
from src.domain.models import BookMetadata


class ParseMetadataCommand:

    def __init__(self, parser: BookMetadataParser):
        self._parser = parser

    def execute(self, book_id: int) -> BookMetadata:
        html_files = glob.glob(f"books/{book_id}/*.html")
        if not html_files:
            return None

        with open(html_files[0], 'r', encoding='utf-8') as f:
            content = f.read()

        return self._parser.parse(content)
