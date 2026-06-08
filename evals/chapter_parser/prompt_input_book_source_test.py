"""Tests for PromptInputBookSource."""
from evals.chapter_parser.prompt_input_book_source import PromptInputBookSource
from src.prompts.chapter_parser.input import (
    PromptInput,
    PromptInputChapter,
    PromptInputMetadata,
    PromptInputSection,
)


def _make_input() -> PromptInput:
    return PromptInput(
        metadata=PromptInputMetadata(title="Pride and Prejudice", author="Austen"),
        chapters=[
            PromptInputChapter(
                id=1,
                sections=[
                    PromptInputSection(
                        id=1,
                        text="Pride and Prejudice, by Austen.",
                        type="book_title_announcement",
                    ),
                    PromptInputSection(
                        id=2, text="Chapter 1.", type="chapter_announcement",
                    ),
                    PromptInputSection(id=3, text="Hello world.", type="text"),
                ],
            ),
        ],
    )


def test_get_book_strips_announcement_sections() -> None:
    # Arrange
    source = PromptInputBookSource(_make_input())

    # Act
    ctx = source.get_book(url="ignored")

    # Assert
    chapter = ctx.book.content.chapters[0]
    assert [s.text for s in chapter.sections] == ["Hello world."]
    assert [s.section_type for s in chapter.sections] == ["text"]


def test_get_book_returns_metadata_and_chapter_number() -> None:
    # Arrange
    source = PromptInputBookSource(_make_input())

    # Act
    ctx = source.get_book(url="ignored")

    # Assert
    assert ctx.book.metadata.title == "Pride and Prejudice"
    assert ctx.book.metadata.author == "Austen"
    assert ctx.book.content.chapters[0].number == 1
    assert [c.number for c in ctx.chapters_to_parse] == [1]


def test_get_book_treats_blank_author_as_none() -> None:
    # Arrange
    prompt_input = PromptInput(
        metadata=PromptInputMetadata(title="T", author=""),
        chapters=[PromptInputChapter(id=1, sections=[])],
    )
    source = PromptInputBookSource(prompt_input)

    # Act
    ctx = source.get_book(url="ignored")

    # Assert
    assert ctx.book.metadata.author is None
