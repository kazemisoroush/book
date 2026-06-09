"""Tests for domain models."""
from .character import NARRATOR_ID, Character, make_default_narrator
from .character_registry import CharacterRegistry
from .models import (
    Beat,
    BeatType,
    Book,
    BookContent,
    BookMetadata,
    Chapter,
    Section,
)


class TestBeatIs:
    """Tests for Beat type predicates."""

    def test_illustration_predicates(self) -> None:
        # Arrange
        beat = Beat(text="[Illustration]", beat_type=BeatType.ILLUSTRATION)

        # Act / Assert
        assert beat.is_illustration()
        assert not beat.is_narration()
        assert not beat.is_dialogue()
        assert not beat.is_narratable

    def test_dialogue_and_narration_are_narratable(self) -> None:
        # Arrange
        dialogue = Beat(text="Hi", beat_type=BeatType.DIALOGUE, character_id=2)
        narration = Beat(text="She said.", beat_type=BeatType.NARRATION, character_id=NARRATOR_ID)

        # Act / Assert
        assert dialogue.is_narratable
        assert narration.is_narratable

    def test_chapter_announcement_and_book_title_are_narratable(self) -> None:
        # Arrange
        chapter = Beat(text="Chapter One.", beat_type=BeatType.CHAPTER_ANNOUNCEMENT, character_id=NARRATOR_ID)
        title = Beat(text="Pride and Prejudice.", beat_type=BeatType.BOOK_TITLE, character_id=NARRATOR_ID)

        # Act / Assert
        assert chapter.is_narratable
        assert title.is_narratable
        assert chapter.is_chapter_announcement()
        assert not title.is_chapter_announcement()

    def test_vocal_effect_and_copyright_and_other_not_narratable(self) -> None:
        # Arrange
        vocal = Beat(text="breath", beat_type=BeatType.VOCAL_EFFECT, character_id=2)
        copyright_ = Beat(text="Copyright 2020", beat_type=BeatType.COPYRIGHT)
        other = Beat(text="{6}", beat_type=BeatType.OTHER)

        # Act / Assert
        assert not vocal.is_narratable
        assert not copyright_.is_narratable
        assert not other.is_narratable
        assert copyright_.is_copyright()
        assert other.is_other()


class TestBookSerialization:
    """Tests for Book.to_dict / Book.from_dict."""

    def _metadata(self) -> BookMetadata:
        return BookMetadata(
            title="Test", author="Author", releaseDate=None,
            language="en", originalPublication=None, credits=None,
        )

    def test_to_dict_emits_metadata_and_content(self) -> None:
        # Arrange
        chapter = Chapter(number=1, title="Ch I", sections=[Section(text="Hello.")])
        book = Book(metadata=self._metadata(), content=BookContent(chapters=[chapter]))

        # Act
        result = book.to_dict()

        # Assert
        assert result["metadata"]["title"] == "Test"
        assert result["content"]["chapters"][0]["title"] == "Ch I"
        assert result["content"]["chapters"][0]["sections"][0]["text"] == "Hello."
        assert "beats" not in result["content"]["chapters"][0]

    def test_to_dict_omits_empty_character_registry(self) -> None:
        # Arrange
        book = Book(metadata=self._metadata(), content=BookContent(chapters=[]))

        # Act
        result = book.to_dict()

        # Assert
        assert "character_registry" not in result

    def test_to_dict_omits_empty_voice_assignments(self) -> None:
        # Arrange
        book = Book(metadata=self._metadata(), content=BookContent(chapters=[]))

        # Act
        result = book.to_dict()

        # Assert
        assert "voice_assignments" not in result

    def test_to_dict_includes_character_registry_when_populated(self) -> None:
        # Arrange
        registry = CharacterRegistry(characters=[
            Character(id=1, name="Narrator"),
            Character(id=2, name="Alice"),
        ])
        book = Book(
            metadata=self._metadata(),
            content=BookContent(chapters=[]),
            character_registry=registry,
        )

        # Act
        result = book.to_dict()

        # Assert
        assert [c["id"] for c in result["character_registry"]] == [1, 2]

    def test_to_dict_includes_voice_assignments_when_populated(self) -> None:
        # Arrange
        book = Book(
            metadata=self._metadata(),
            content=BookContent(chapters=[]),
            voice_assignments={1: "v_narr", 2: "v_alice"},
        )

        # Act
        result = book.to_dict()

        # Assert
        assert result["voice_assignments"] == {"1": "v_narr", "2": "v_alice"}

    def test_round_trip_preserves_beat_fields(self) -> None:
        # Arrange
        beat = Beat(
            text="hi", beat_type=BeatType.DIALOGUE,
            character_id=2, emotion="warm",
        )
        chapter = Chapter(number=1, title="Ch I", beats=[beat])
        book = Book(metadata=self._metadata(), content=BookContent(chapters=[chapter]))

        # Act
        restored = Book.from_dict(book.to_dict())

        # Assert
        restored_beat = restored.content.chapters[0].beats[0]
        assert restored_beat.text == "hi"
        assert restored_beat.beat_type == BeatType.DIALOGUE
        assert restored_beat.character_id == 2
        assert restored_beat.emotion == "warm"

    def test_round_trip_preserves_voice_assignments(self) -> None:
        # Arrange
        book = Book(
            metadata=self._metadata(),
            content=BookContent(chapters=[]),
            voice_assignments={1: "v_narr"},
        )

        # Act
        restored = Book.from_dict(book.to_dict())

        # Assert
        assert restored.voice_assignments == {1: "v_narr"}


class TestCharacter:
    """Tests for Character.to_dict / from_dict / voice_design_prompt."""

    def test_to_dict_emits_all_fields(self) -> None:
        # Arrange
        char = Character(
            id=2, name="Alice",
            description="A girl", sex="female", age="young",
        )

        # Act
        result = char.to_dict()

        # Assert
        assert result == {
            "id": 2,
            "name": "Alice",
            "description": "A girl",
            "sex": "female",
            "age": "young",
        }

    def test_from_dict_round_trip(self) -> None:
        # Arrange
        original = Character(id=5, name="Bob", description="A boy", sex="male", age="adult")

        # Act
        restored = Character.from_dict(original.to_dict())

        # Assert
        assert restored == original

    def test_from_dict_missing_optionals_default_to_none(self) -> None:
        # Arrange / Act
        char = Character.from_dict({"id": 7, "name": "Solo"})

        # Assert
        assert char.description is None
        assert char.sex is None
        assert char.age is None

    def test_voice_design_prompt_combines_segments(self) -> None:
        # Arrange
        char = Character(
            id=1, name="N", description="calm voice", sex="male", age="adult",
        )

        # Act / Assert
        assert char.voice_design_prompt == "Age: adult. Sex: male. Description: calm voice."

    def test_voice_design_prompt_none_when_no_description(self) -> None:
        # Arrange
        char = Character(id=1, name="N", sex="male", age="adult")

        # Act / Assert
        assert char.voice_design_prompt is None

    def test_voice_design_prompt_strips_trailing_dot(self) -> None:
        # Arrange
        char = Character(id=1, name="N", description="calm voice.", sex="male")

        # Act / Assert
        assert char.voice_design_prompt == "Sex: male. Description: calm voice."


class TestCharacterRegistry:
    """Tests for CharacterRegistry."""

    def test_default_narrator_has_known_id_and_name(self) -> None:
        # Arrange
        registry = CharacterRegistry(characters=[make_default_narrator()])

        # Act / Assert
        narrator = registry.get(NARRATOR_ID)
        assert narrator is not None
        assert narrator.name == "Narrator"

    def test_get_returns_none_for_unknown_id(self) -> None:
        # Arrange
        registry = CharacterRegistry()

        # Act / Assert
        assert registry.get(999) is None

    def test_upsert_replaces_existing_character(self) -> None:
        # Arrange
        registry = CharacterRegistry(characters=[Character(id=2, name="Old")])

        # Act
        registry.upsert(Character(id=2, name="New"))

        # Assert
        assert len(registry.characters) == 1
        assert registry.get(2).name == "New"  # type: ignore[union-attr]

    def test_upsert_adds_new_character(self) -> None:
        # Arrange
        registry = CharacterRegistry(characters=[Character(id=1, name="Narrator")])

        # Act
        registry.upsert(Character(id=2, name="Alice"))

        # Assert
        assert len(registry.characters) == 2


class TestBookId:
    """Tests for BookMetadata.book_id."""

    def _metadata(self, title: str, author: str | None) -> BookMetadata:
        return BookMetadata(
            title=title, author=author, releaseDate=None,
            language=None, originalPublication=None, credits=None,
        )

    def test_basic_slug(self) -> None:
        # Arrange / Act / Assert
        assert self._metadata("Pride and Prejudice", "Jane Austen").book_id == "pride_and_prejudice:jane_austen"

    def test_strips_trailing_date_range_from_author(self) -> None:
        # Arrange / Act / Assert
        assert self._metadata("Pride and Prejudice", "Austen, Jane, 1775-1817").book_id == "pride_and_prejudice:jane_austen"

    def test_missing_author_falls_back_to_unknown(self) -> None:
        # Arrange / Act / Assert
        assert self._metadata("Solo", None).book_id == "solo:unknown"

    def test_missing_title_falls_back_to_untitled(self) -> None:
        # Arrange / Act / Assert
        assert self._metadata("", "Jane Austen").book_id == "untitled:jane_austen"
