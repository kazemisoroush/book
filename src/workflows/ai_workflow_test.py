"""Tests for AIWorkflow._apply_prompt_output: LLM response → Book mapping."""
from src.domain.beat import BeatType
from src.domain.models import Book, BookContent, BookMetadata, Chapter
from src.prompts.chapter_parser.output import (
    PromptOutput,
    PromptOutputBeat,
    PromptOutputChapter,
    PromptOutputCharacter,
)
from src.workflows.ai_workflow import AIWorkflow


def _empty_book() -> Book:
    metadata = BookMetadata(
        title="Pride and Prejudice", author="Jane Austen",
        releaseDate=None, language=None,
        originalPublication=None, credits=None,
    )
    return Book(metadata=metadata, content=BookContent(chapters=[]))


def _chapter() -> Chapter:
    return Chapter(number=1, title="", sections=[])


def _response() -> PromptOutput:
    return PromptOutput(
        chapters=[PromptOutputChapter(
            id=1,
            beats=[
                PromptOutputBeat(
                    id=1, type="narration", text="Hello.", char_id=1,
                    emotion="neutral",
                ),
                PromptOutputBeat(
                    id=2, type="dialogue", text="My dear.", char_id=2,
                    emotion="warmly insistent",
                ),
            ],
        )],
        characters=[
            PromptOutputCharacter(
                id=1, name="Narrator",
                description="A measured English reading voice.",
                sex="neutral", age="adult",
            ),
            PromptOutputCharacter(
                id=2, name="Mrs. Bennet",
                description="A warm, excitable middle-aged Englishwoman.",
                sex="female", age="adult",
            ),
        ],
    )


def test_characters_are_upserted_with_description_sex_age() -> None:
    # Arrange
    book = _empty_book()
    chapter = _chapter()

    # Act
    AIWorkflow._apply_prompt_output(book, chapter, _response())

    # Assert
    chars = {c.name: c for c in book.character_registry.characters}
    assert chars["Narrator"].description == "A measured English reading voice."
    assert chars["Mrs. Bennet"].description == "A warm, excitable middle-aged Englishwoman."
    assert chars["Mrs. Bennet"].sex == "female"
    assert chars["Mrs. Bennet"].age == "adult"


def test_numeric_char_id_maps_to_string_character_id_on_beats() -> None:
    # Arrange
    book = _empty_book()
    chapter = _chapter()

    # Act
    AIWorkflow._apply_prompt_output(book, chapter, _response())

    # Assert
    beats = book.content.chapters[0].sections[0].beats
    assert beats is not None
    book_id = book.book_id
    assert beats[0].character_id == f"{book_id}:narrator"
    assert beats[1].character_id == f"{book_id}:mrs_bennet"


def test_beat_text_emotion_and_type_round_trip() -> None:
    # Arrange
    book = _empty_book()
    chapter = _chapter()

    # Act
    AIWorkflow._apply_prompt_output(book, chapter, _response())

    # Assert
    beats = book.content.chapters[0].sections[0].beats
    assert beats is not None
    assert [b.text for b in beats] == ["Hello.", "My dear."]
    assert [b.beat_type for b in beats] == [BeatType.NARRATION, BeatType.DIALOGUE]
    assert [b.emotion for b in beats] == ["neutral", "warmly insistent"]


def test_chapter_sections_replaced_with_single_beats_section() -> None:
    # Arrange
    book = _empty_book()
    chapter = _chapter()

    # Act
    AIWorkflow._apply_prompt_output(book, chapter, _response())

    # Assert
    new_sections = book.content.chapters[0].sections
    assert len(new_sections) == 1
    assert new_sections[0].text == ""
    assert new_sections[0].beats is not None
    assert len(new_sections[0].beats) == 2


def test_unknown_beat_type_falls_back_to_narration() -> None:
    # Arrange
    book = _empty_book()
    chapter = _chapter()
    response = PromptOutput(
        chapters=[PromptOutputChapter(
            id=1,
            beats=[PromptOutputBeat(
                id=1, type="not_a_real_type", text="x", char_id=1,
            )],
        )],
        characters=[PromptOutputCharacter(id=1, name="Narrator")],
    )

    # Act
    AIWorkflow._apply_prompt_output(book, chapter, response)

    # Assert
    beats = book.content.chapters[0].sections[0].beats
    assert beats is not None
    assert beats[0].beat_type == BeatType.NARRATION
