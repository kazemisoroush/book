from bs4 import BeautifulSoup
from src.parsers.book_content_parser import BookContentParser
from src.domain.models import BookContent, Chapter, Section


class StaticProjectGutenbergHTMLContentParser(BookContentParser):

    def parse(self, content: str) -> BookContent:
        soup = BeautifulSoup(content, 'html.parser')
        chapters = []
        chapter_number = 0

        chapter_headings = soup.find_all('h2')

        for i, heading in enumerate(chapter_headings):
            heading_text = heading.get_text(strip=True)
            if 'CHAPTER' in heading_text.upper():
                chapter_number += 1
                next_heading = chapter_headings[i + 1] if i + 1 < len(chapter_headings) else None
                sections = self._extract_sections(heading, next_heading)
                chapters.append(Chapter(
                    number=chapter_number,
                    title=heading_text,
                    sections=sections
                ))

        return BookContent(chapters=chapters)

    def _extract_sections(self, start_heading, end_heading) -> list[Section]:
        sections = []
        current = start_heading.find_next_sibling()

        while current and current != end_heading:
            if current.name == 'p':
                text = current.get_text(strip=True)
                if text:
                    sections.append(Section(text=text))
            current = current.find_next_sibling()

        return sections
