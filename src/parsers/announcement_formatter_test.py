"""Tests for AnnouncementFormatter."""
from src.ai.ai_provider import AIProvider
from src.domain.models import AIPrompt
from src.parsers.announcement_formatter import AnnouncementFormatter


class _FakeAIProvider(AIProvider):
    """Returns the response verbatim; records prompts for inspection."""

    def __init__(self, response: str) -> None:
        self._response = response
        self.last_prompt: str | None = None
        self.last_ai_prompt: AIPrompt | None = None

    def generate(self, prompt: AIPrompt, max_tokens: int = 1000) -> str:
        self.last_prompt = prompt.build_full_prompt()
        self.last_ai_prompt = prompt
        return self._response


class TestFormatBookTitle:
    """AnnouncementFormatter.format_book_title produces clean spoken text."""

    def test_returns_llm_response_stripped(self) -> None:
        """The formatter returns the LLM response with whitespace and quotes stripped."""
        # Arrange
        provider = _FakeAIProvider('  "Pride and Prejudice, by Jane Austen."  ')
        formatter = AnnouncementFormatter(provider)

        # Act
        result = formatter.format_book_title("Pride and Prejudice", "Austen, Jane, 1775-1817")

        # Assert
        assert result == "Pride and Prejudice, by Jane Austen."

    def test_prompt_contains_title_and_author(self) -> None:
        """The prompt sent to the LLM includes the raw title and author."""
        # Arrange
        provider = _FakeAIProvider("Moby Dick, by Herman Melville.")
        formatter = AnnouncementFormatter(provider)

        # Act
        formatter.format_book_title("Moby Dick", "Melville, Herman, 1819-1891")

        # Assert
        assert provider.last_prompt is not None
        assert "Moby Dick" in provider.last_prompt
        assert "Melville, Herman, 1819-1891" in provider.last_prompt

    def test_handles_none_author(self) -> None:
        """When author is None, the prompt still works."""
        # Arrange
        provider = _FakeAIProvider("Beowulf.")
        formatter = AnnouncementFormatter(provider)

        # Act
        result = formatter.format_book_title("Beowulf", None)

        # Assert
        assert result == "Beowulf."

    def test_prompt_puts_input_in_dynamic_portion(self) -> None:
        """Title and author must be in the dynamic portion (user message), not static."""
        # Arrange
        provider = _FakeAIProvider("Pride and Prejudice, by Jane Austen.")
        formatter = AnnouncementFormatter(provider)

        # Act
        formatter.format_book_title("Pride and Prejudice", "Austen, Jane, 1775-1817")

        # Assert
        assert provider.last_ai_prompt is not None
        dynamic = provider.last_ai_prompt.build_dynamic_portion()
        assert "Pride and Prejudice" in dynamic
        assert "Austen, Jane, 1775-1817" in dynamic
        assert dynamic.strip() != ""


class TestFormatChapterAnnouncement:
    """AnnouncementFormatter.format_chapter_announcement produces clean spoken text."""

    def test_returns_llm_response_stripped(self) -> None:
        """The formatter returns the LLM response with whitespace and quotes stripped."""
        # Arrange
        provider = _FakeAIProvider('  "Chapter One. The Beginning."  ')
        formatter = AnnouncementFormatter(provider)

        # Act
        result = formatter.format_chapter_announcement(1, "The Beginning")

        # Assert
        assert result == "Chapter One. The Beginning."

    def test_prompt_contains_chapter_number_and_title(self) -> None:
        """The prompt sent to the LLM includes the chapter number and title."""
        # Arrange
        provider = _FakeAIProvider("Chapter Five. Into the Woods.")
        formatter = AnnouncementFormatter(provider)

        # Act
        formatter.format_chapter_announcement(5, "Into the Woods")

        # Assert
        assert provider.last_prompt is not None
        assert "5" in provider.last_prompt
        assert "Into the Woods" in provider.last_prompt

    def test_prompt_puts_input_in_dynamic_portion(self) -> None:
        """Chapter number and title must be in the dynamic portion (user message)."""
        # Arrange
        provider = _FakeAIProvider("Chapter Three. The Storm.")
        formatter = AnnouncementFormatter(provider)

        # Act
        formatter.format_chapter_announcement(3, "The Storm")

        # Assert
        assert provider.last_ai_prompt is not None
        dynamic = provider.last_ai_prompt.build_dynamic_portion()
        assert "3" in dynamic
        assert "The Storm" in dynamic
        assert dynamic.strip() != ""
