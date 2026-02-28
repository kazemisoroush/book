from bs4 import BeautifulSoup
from src.parsers.book_metadata_parser import BookMetadataParser
from src.domain.models import BookMetadata


class StaticProjectGutenbergHTMLMetadataParser(BookMetadataParser):

    def parse(self, content: str) -> BookMetadata:
        soup = BeautifulSoup(content, 'html.parser')

        title = self._extract_meta_content(soup, 'dc.title')
        author = self._extract_meta_content(soup, 'dc.creator')
        language = self._extract_meta_content(soup, 'dc.language')
        release_date = self._extract_meta_content(soup, 'dcterms.created')

        return BookMetadata(
            title=title,
            author=author,
            releaseDate=release_date,
            language=language,
            originalPublication=None,
            credits=None
        )

    def _extract_meta_content(self, soup: BeautifulSoup, meta_name: str) -> str:
        meta_tag = soup.find('meta', attrs={'name': meta_name})
        if meta_tag and meta_tag.get('content'):
            return meta_tag.get('content')
        return None
