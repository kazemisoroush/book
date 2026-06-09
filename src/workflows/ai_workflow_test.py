"""Tests for AIWorkflow._apply_prompt_output: LLM response → Book mapping."""
from src.domain.beat import BeatType
from src.domain.character import Character
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
    return Chapter(number=1, title="")


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


def test_characters_are_upserted_with_int_ids_and_description() -> None:
    # Arrange
    book = _empty_book()
    chapter = _chapter()

    # Act
    AIWorkflow._apply_prompt_output(book, chapter, _response())

    # Assert
    chars = {c.id: c for c in book.character_registry.characters}
    assert chars[1].name == "Narrator"
    assert chars[2].name == "Mrs. Bennet"
    assert chars[1].description == "A measured English reading voice."
    assert chars[2].description == "A warm, excitable middle-aged Englishwoman."
    assert chars[2].sex == "female"
    assert chars[2].age == "adult"


def test_beat_character_id_is_the_llm_numeric_id() -> None:
    # Arrange
    book = _empty_book()
    chapter = _chapter()

    # Act
    AIWorkflow._apply_prompt_output(book, chapter, _response())

    # Assert
    beats = book.content.chapters[0].beats
    assert beats[0].character_id == 1
    assert beats[1].character_id == 2


def test_beat_text_emotion_and_type_round_trip() -> None:
    # Arrange
    book = _empty_book()
    chapter = _chapter()

    # Act
    AIWorkflow._apply_prompt_output(book, chapter, _response())

    # Assert
    beats = book.content.chapters[0].beats
    assert [b.text for b in beats] == ["Hello.", "My dear."]
    assert [b.beat_type for b in beats] == [BeatType.NARRATION, BeatType.DIALOGUE]
    assert [b.emotion for b in beats] == ["neutral", "warmly insistent"]


def test_chapter_sections_cleared_and_beats_populated() -> None:
    # Arrange
    book = _empty_book()
    chapter = _chapter()

    # Act
    AIWorkflow._apply_prompt_output(book, chapter, _response())

    # Assert
    stored_chapter = book.content.chapters[0]
    assert stored_chapter.sections == []
    assert len(stored_chapter.beats) == 2


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
    assert book.content.chapters[0].beats[0].beat_type == BeatType.NARRATION


def test_build_prompt_input_threads_known_characters_into_the_prompt() -> None:
    # Arrange
    metadata = BookMetadata(
        title="Alice's Adventures in Wonderland", author="Lewis Carroll",
        releaseDate=None, language=None, originalPublication=None, credits=None,
    )
    chapter = Chapter(number=2, title="The Pool of Tears")
    known = [
        Character(id=1, name="Narrator", sex="neutral", age="adult"),
        Character(id=2, name="Alice", sex="female", age="young"),
    ]

    # Act
    result = AIWorkflow._build_prompt_input(metadata, chapter, known_characters=known)

    # Assert
    assert [c.id for c in result.characters] == [1, 2]
    assert [c.name for c in result.characters] == ["Narrator", "Alice"]


def test_build_prompt_input_defaults_to_empty_characters() -> None:
    # Arrange
    metadata = BookMetadata(
        title="T", author="A", releaseDate=None,
        language=None, originalPublication=None, credits=None,
    )
    chapter = Chapter(number=1, title="")

    # Act
    result = AIWorkflow._build_prompt_input(metadata, chapter)

    # Assert
    assert result.characters == []
