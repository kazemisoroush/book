"""Parser for Project Gutenberg HTML book metadata.

Extracts structured metadata (title, author, language, etc.) from Project Gutenberg
HTML files. Supports both newer Dublin Core <meta> tags and older div-based format.
"""
from typing import Optional

from bs4 import BeautifulSoup

from src.domain.models import BookMetadata
from src.parsers.book_metadata_parser import BookMetadataParser


class StaticProjectGutenbergHTMLMetadataParser(BookMetadataParser):
    """Parser for Project Gutenberg HTML metadata.

    Supports two formats:
    1. Newer format: ``<meta>`` tags with Dublin Core attributes
       (dc.title, dc.creator, dc.language, dcterms.created).
    2. Older format: ``<div>`` elements whose text begins with a known
       label such as "Title:", "Author:", "Release Date:", "Language:",
       or "Produced by:".

    When both formats are present, the ``<meta>`` tag values take
    priority over the div-based values.
    """

    def parse(self, content: str) -> BookMetadata:
        """Parse metadata from Project Gutenberg HTML content.

        Args:
            content: Raw HTML content from a Project Gutenberg book file.

        Returns:
            BookMetadata with extracted title, author, and other fields.
        """
        soup = BeautifulSoup(content, 'html.parser')

        # --- Primary: Dublin Core <meta> tags (newer PG format) ---
        title: Optional[str] = self._extract_meta_content(soup, 'dc.title')
        author: Optional[str] = self._extract_meta_content(soup, 'dc.creator')
        language: Optional[str] = self._extract_meta_content(soup, 'dc.language')
        release_date: Optional[str] = self._extract_meta_content(soup, 'dcterms.created')
        credits: Optional[str] = None

        # --- Fallback: div-based plain-text labels (older PG format) ---
        if not title or not author or not language or not release_date:
            div_meta = self._extract_div_metadata(soup)
            if not title:
                title = div_meta.get('title')
            if not author:
                author = div_meta.get('author')
            if not language:
                language = div_meta.get('language')
            if not release_date:
                release_date = div_meta.get('release_date')
            if not credits:
                credits = div_meta.get('credits')

        return BookMetadata(
            title=title or "",
            author=author,
            releaseDate=release_date,
            language=language,
            originalPublication=None,
            credits=credits,
        )

    def _extract_meta_content(
        self, soup: BeautifulSoup, meta_name: str
    ) -> Optional[str]:
        meta_tag = soup.find('meta', attrs={'name': meta_name})
        if meta_tag:
            value = meta_tag.get('content')
            if value and isinstance(value, str):
                return value
        return None

    def _extract_div_metadata(self, soup: BeautifulSoup) -> dict:
        """Scan all <div> elements for known plain-text metadata labels.

        For each div, the first text node before any <br> tag is examined.
        If it starts with a recognised label (e.g. "Title:") the value
        after the colon is returned.

        Returns:
            dict with keys: title, author, release_date, language, credits
        """
        result: dict = {}

        label_map = {
            'title:': 'title',
            'author:': 'author',
            'release date:': 'release_date',
            'language:': 'language',
            'produced by:': 'credits',
        }

        for div in soup.find_all('div'):
            # Use only the text before the first <br> tag, if any.
            br = div.find('br')
            if br:
                # Collect only the direct NavigableString children before the <br>.
                text_parts = []
                for child in div.children:
                    if child == br:
                        break
                    if hasattr(child, 'get_text'):
                        text_parts.append(child.get_text())
                    else:
                        text_parts.append(str(child))
                div_text = ''.join(text_parts).strip()
            else:
                div_text = div.get_text(strip=True)

            lower = div_text.lower()
            for label, key in label_map.items():
                if lower.startswith(label):
                    value = div_text[len(label):].strip()
                    if value and key not in result:
                        result[key] = value
                    break

        return result
