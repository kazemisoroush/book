"""Formats book title and chapter announcement text for natural narration.

Uses a lightweight LLM call to convert raw metadata (which may contain
messy author names like "Austen, Jane, 1775-1817") into clean spoken-form
text suitable for TTS narration (e.g. "Pride and Prejudice, by Jane Austen").
"""
from typing import Optional

import structlog

from src.ai.ai_provider import AIProvider
from src.domain.models import AIPrompt

logger = structlog.get_logger(__name__)

_BOOK_TITLE_PROMPT = """\
Convert the following book metadata into a single short spoken introduction \
suitable for an audiobook narrator to read aloud.

Rules:
- Use natural spoken English
- Format: "<Title>, by <Author>." or just "<Title>." if no author
- Clean up the author name: remove birth/death years, fix inverted names \
(e.g. "Austen, Jane, 1775-1817" → "Jane Austen")
- Do not add any extra commentary, quotes, or formatting
- Return ONLY the spoken text, nothing else

Title: {title}
Author: {author}
"""

_CHAPTER_ANNOUNCEMENT_PROMPT = """\
Convert the following chapter heading into a single short spoken announcement \
suitable for an audiobook narrator to read aloud.

Rules:
- Use natural spoken English
- Convert numeric chapter numbers to words (e.g. "Chapter 1" → "Chapter One")
- If the chapter has a meaningful title, include it naturally \
(e.g. "Chapter One. The Beginning.")
- If the title is just the chapter number repeated or is empty, keep it short \
(e.g. just "Chapter One.")
- Do not add any extra commentary, quotes, or formatting
- Return ONLY the spoken text, nothing else

Chapter number: {number}
Chapter title: {title}
"""


class AnnouncementFormatter:
    """Formats announcement text using a lightweight LLM call.

    Converts raw book metadata and chapter headings into clean, natural
    spoken text for TTS narration. Each call is a small, cheap LLM request
    (~50 tokens output).
    """

    def __init__(self, ai_provider: AIProvider) -> None:
        self._ai_provider = ai_provider

    def format_book_title(
        self,
        title: str,
        author: Optional[str] = None,
    ) -> str:
        """Format a book title and author into natural spoken introduction text.

        Args:
            title: The book title (e.g. "Pride and Prejudice")
            author: The raw author string (e.g. "Austen, Jane, 1775-1817")

        Returns:
            Clean spoken text (e.g. "Pride and Prejudice, by Jane Austen.")
        """
        prompt_text = _BOOK_TITLE_PROMPT.format(
            title=title or "Untitled",
            author=author or "Unknown",
        )
        prompt = AIPrompt(
            static_instructions=prompt_text,
            book_context="",
            character_registry="",
            surrounding_context="",
            scene_registry="",
            text_to_segment="",
        )
        result = self._ai_provider.generate(prompt, max_tokens=100)
        formatted = result.strip().strip('"').strip("'")
        logger.debug("announcement_formatted_book_title", raw_title=title, raw_author=author, formatted=formatted)
        return formatted

    def format_chapter_announcement(
        self,
        chapter_number: int,
        chapter_title: str,
    ) -> str:
        """Format a chapter heading into natural spoken announcement text.

        Args:
            chapter_number: The chapter number (e.g. 1)
            chapter_title: The chapter title (e.g. "The Beginning")

        Returns:
            Clean spoken text (e.g. "Chapter One. The Beginning.")
        """
        prompt_text = _CHAPTER_ANNOUNCEMENT_PROMPT.format(
            number=chapter_number,
            title=chapter_title,
        )
        prompt = AIPrompt(
            static_instructions=prompt_text,
            book_context="",
            character_registry="",
            surrounding_context="",
            scene_registry="",
            text_to_segment="",
        )
        result = self._ai_provider.generate(prompt, max_tokens=100)
        formatted = result.strip().strip('"').strip("'")
        logger.debug(
            "announcement_formatted_chapter",
            chapter_number=chapter_number, chapter_title=chapter_title, formatted=formatted,
        )
        return formatted
