"""Formats book title and chapter announcement text for natural narration.

Uses a lightweight LLM call to convert raw metadata (which may contain
messy author names like "Austen, Jane, 1775-1817") into clean spoken-form
text suitable for TTS narration (for example "Pride and Prejudice, by
Jane Austen"). The prompt classes own their template files, so this
runner only handles the build, call, and post-process flow.
"""
from typing import Optional

import structlog

from src.ai.ai_provider import AIProvider
from src.prompts.models.book_title_prompt import BookTitleAnnouncementPrompt
from src.prompts.models.chapter_announcement_prompt import ChapterAnnouncementPrompt

logger = structlog.get_logger(__name__)


class AnnouncementFormatter:
    """Formats announcement text using a lightweight LLM call.

    Converts raw book metadata and chapter headings into clean, natural
    spoken text for TTS narration. Each call is a small, cheap LLM request
    (about 50 output tokens).
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
            title: The book title (for example "Pride and Prejudice")
            author: The raw author string (for example "Austen, Jane, 1775-1817")

        Returns:
            Clean spoken text (for example "Pride and Prejudice, by Jane Austen.")
        """
        prompt = BookTitleAnnouncementPrompt(title=title, author=author)
        result = self._ai_provider.generate(prompt, max_tokens=100)
        formatted = result.strip().strip('"').strip("'")
        logger.debug(
            "announcement_formatted_book_title",
            raw_title=title, raw_author=author, formatted=formatted,
        )
        return formatted

    def format_chapter_announcement(
        self,
        chapter_number: int,
        chapter_title: str,
    ) -> str:
        """Format a chapter heading into natural spoken announcement text.

        Args:
            chapter_number: The chapter number (for example 1)
            chapter_title: The chapter title (for example "The Beginning")

        Returns:
            Clean spoken text (for example "Chapter One. The Beginning.")
        """
        prompt = ChapterAnnouncementPrompt(
            chapter_number=chapter_number,
            chapter_title=chapter_title,
        )
        result = self._ai_provider.generate(prompt, max_tokens=100)
        formatted = result.strip().strip('"').strip("'")
        logger.debug(
            "announcement_formatted_chapter",
            chapter_number=chapter_number, chapter_title=chapter_title, formatted=formatted,
        )
        return formatted
