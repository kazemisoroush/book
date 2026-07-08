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

    def test_source_url_survives_a_round_trip(self) -> None:
        # Arrange
        book = Book(
            metadata=self._metadata(),
            content=BookContent(chapters=[]),
            source_url="http://example/pg.zip",
        )

        # Act
        restored = Book.from_dict(book.to_dict())

        # Assert
        assert restored.source_url == "http://example/pg.zip"

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

    def test_to_dict_drops_null_beat_attributes(self) -> None:
        # Arrange
        beat = Beat(
            text="plain.", beat_type=BeatType.NARRATION,
            character_id=1, emotion=None, voice_settings=None, voice_id=None,
        )
        chapter = Chapter(number=1, title="Ch I", beats=[beat])
        book = Book(metadata=self._metadata(), content=BookContent(chapters=[chapter]))

        # Act
        result = book.to_dict()

        # Assert
        beat_dict = result["content"]["chapters"][0]["beats"][0]
        assert "emotion" not in beat_dict
        assert "voice_settings" not in beat_dict
        assert "voice_id" not in beat_dict
        assert beat_dict["text"] == "plain."
        assert beat_dict["beat_type"] == "narration"
        assert beat_dict["character_id"] == 1

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

    def test_round_trip_preserves_label(self) -> None:
        # Arrange
        chapter = Chapter(number=1, title="Letter 1", label="Letter 1")
        book = Book(metadata=self._metadata(), content=BookContent(chapters=[chapter]))

        # Act
        restored = Book.from_dict(book.to_dict())

        # Assert
        assert restored.content.chapters[0].label == "Letter 1"

    def test_to_dict_omits_label_when_none(self) -> None:
        # Arrange
        chapter = Chapter(number=1, title="Ch I")
        book = Book(metadata=self._metadata(), content=BookContent(chapters=[chapter]))

        # Act
        result = book.to_dict()

        # Assert
        assert "label" not in result["content"]["chapters"][0]


class TestCharacter:
    """Tests for Character.to_dict / from_dict."""

    def test_to_dict_emits_all_fields(self) -> None:
        # Arrange
        char = Character(
            id=2, name="Alice",
            gender="female", age="young", accent="british",
        )

        # Act
        result = char.to_dict()

        # Assert
        assert result == {
            "id": 2,
            "name": "Alice",
            "gender": "female",
            "age": "young",
            "accent": "british",
        }

    def test_from_dict_round_trip(self) -> None:
        # Arrange
        original = Character(
            id=5, name="Bob",
            gender="male", age="middle_aged", accent="american",
        )

        # Act
        restored = Character.from_dict(original.to_dict())

        # Assert
        assert restored == original

    def test_from_dict_accepts_legacy_sex_field(self) -> None:
        # Arrange / Act
        char = Character.from_dict({
            "id": 9, "name": "Old", "sex": "male", "age": "old",
        })

        # Assert
        assert char.gender == "male"

    def test_from_dict_missing_optionals_default_to_none(self) -> None:
        # Arrange / Act
        char = Character.from_dict({"id": 7, "name": "Solo"})

        # Assert
        assert char.gender is None
        assert char.age is None
        assert char.accent is None


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


class TestChapterDisplayName:
    """Chapter.display_name renders the human-readable label used by Studio + announcements."""

    def test_display_name_uses_number(self) -> None:
        # Arrange / Act / Assert
        assert Chapter(number=1, title="").display_name == "Chapter 1"
        assert Chapter(number=27, title="Anything").display_name == "Chapter 27"

    def test_display_name_uses_label_when_set(self) -> None:
        # Arrange / Act / Assert
        assert Chapter(number=1, title="Letter 1", label="Letter 1").display_name == "Letter 1"
        assert Chapter(number=5, title="Epilogue", label="Epilogue").display_name == "Epilogue"

    def test_display_name_falls_back_when_no_label(self) -> None:
        # Arrange / Act / Assert
        assert Chapter(number=3, title="CHAPTER III.").display_name == "Chapter 3"
        assert Chapter(number=3, title="CHAPTER III.", label=None).display_name == "Chapter 3"


class TestChapterDirSlug:
    """Chapter.dir_slug renders the zero-padded file-system label."""

    def test_dir_slug_zero_pads_to_three_digits(self) -> None:
        # Arrange / Act / Assert
        assert Chapter(number=1, title="").dir_slug == "chapter_001"
        assert Chapter(number=27, title="").dir_slug == "chapter_027"
        assert Chapter(number=999, title="").dir_slug == "chapter_999"


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


class TestDisplayAuthor:
    """Tests for BookMetadata.display_author."""

    def _metadata(self, author: str | None) -> BookMetadata:
        return BookMetadata(
            title="A Book", author=author, releaseDate=None,
            language=None, originalPublication=None, credits=None,
        )

    def test_flips_last_first_and_strips_dates(self) -> None:
        # Arrange / Act / Assert
        assert self._metadata("Brontë, Emily, 1818-1848").display_author == "Emily Brontë"

    def test_missing_author_is_none(self) -> None:
        # Arrange / Act / Assert
        assert self._metadata(None).display_author is None
