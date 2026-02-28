import glob
from src.parsers.book_content_parser import BookContentParser
from src.domain.models import BookContent


class ParseContentCommand:

    def __init__(self, parser: BookContentParser):
        self._parser = parser

    def execute(self, book_id: int) -> BookContent:
        html_files = glob.glob(f"books/{book_id}/*.html")
        if not html_files:
            return None

        with open(html_files[0], 'r', encoding='utf-8') as f:
            content = f.read()

        return self._parser.parse(content)
