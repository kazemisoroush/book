"""Tests for domain models."""
import pytest
from dataclasses import FrozenInstanceError
from .models import (
    Segment, SegmentType, Section, Chapter, Book, BookMetadata, BookContent,
    Character, CharacterRegistry, Scene, SceneRegistry, AIPrompt,
)


class TestSegment:
    """Tests for Segment model."""

    def test_is_illustration_returns_true_for_illustration_type(self) -> None:
        """is_illustration() returns True for ILLUSTRATION segment type."""
        # Arrange
        segment = Segment(text="[Illustration]", segment_type=SegmentType.ILLUSTRATION)

        # Act / Assert
        assert segment.is_illustration()
        assert not segment.is_narration()
        assert not segment.is_dialogue()

    def test_is_copyright_returns_true_for_copyright_type(self) -> None:
        """is_copyright() returns True for COPYRIGHT segment type."""
        # Arrange
        segment = Segment(text="Copyright 2020", segment_type=SegmentType.COPYRIGHT)

        # Act / Assert
        assert segment.is_copyright()
        assert not segment.is_narration()

    def test_is_other_returns_true_for_other_type(self) -> None:
        """is_other() returns True for OTHER segment type."""
        # Arrange
        segment = Segment(text="{6}", segment_type=SegmentType.OTHER)

        # Act / Assert
        assert segment.is_other()
        assert not segment.is_narration()

    def test_is_narratable_true_for_dialogue_and_narration(self) -> None:
        """is_narratable() returns True for segments that should be read aloud."""
        # Arrange
        dialogue = Segment(text="Hello", segment_type=SegmentType.DIALOGUE, character_id="alice")
        narration = Segment(text="She said.", segment_type=SegmentType.NARRATION, character_id="narrator")

        # Act / Assert
        assert dialogue.is_narratable
        assert narration.is_narratable

    def test_is_narratable_false_for_non_audio_types(self) -> None:
        """is_narratable() returns False for illustration, copyright, and other."""
        # Arrange
        illustration = Segment(text="[Illustration]", segment_type=SegmentType.ILLUSTRATION)
        copyright_ = Segment(text="Copyright 2020", segment_type=SegmentType.COPYRIGHT)
        other = Segment(text="{6}", segment_type=SegmentType.OTHER)

        # Act / Assert
        assert not illustration.is_narratable
        assert not copyright_.is_narratable
        assert not other.is_narratable

    def test_vocal_effect_is_not_narratable(self) -> None:
        """is_narratable returns False for VOCAL_EFFECT segments."""
        # Arrange
        segment = Segment(
            text="soft breath intake",
            segment_type=SegmentType.VOCAL_EFFECT,
            character_id="alice",
        )

        # Act / Assert
        assert not segment.is_narratable

    def test_sound_effect_segment_has_sound_effect_detail_field(self) -> None:
        """SOUND_EFFECT segment can be created with sound_effect_detail field."""
        # Arrange / Act
        segment = Segment(
            text="door knock",
            segment_type=SegmentType.SOUND_EFFECT,
            sound_effect_detail="4 firm knocks on a heavy old wooden door",
        )

        # Assert
        assert segment.text == "door knock"
        assert segment.segment_type == SegmentType.SOUND_EFFECT
        assert segment.sound_effect_detail == "4 firm knocks on a heavy old wooden door"
        assert segment.character_id is None

    def test_sound_effect_segment_detail_is_optional(self) -> None:
        """SOUND_EFFECT segment can be created without sound_effect_detail."""
        # Arrange / Act
        segment = Segment(
            text="dry cough",
            segment_type=SegmentType.SOUND_EFFECT,
        )

        # Assert
        assert segment.text == "dry cough"
        assert segment.sound_effect_detail is None

    def test_chapter_announcement_segment_is_narratable(self) -> None:
        """CHAPTER_ANNOUNCEMENT segments are narratable — TTS reads them aloud."""
        # Arrange
        segment = Segment(
            text="Chapter One.",
            segment_type=SegmentType.CHAPTER_ANNOUNCEMENT,
            character_id="narrator",
        )

        # Act / Assert
        assert segment.is_narratable

    def test_book_title_segment_is_narratable(self) -> None:
        """BOOK_TITLE segments are narratable — TTS reads the title aloud."""
        # Arrange
        segment = Segment(
            text="Pride and Prejudice, by Jane Austen.",
            segment_type=SegmentType.BOOK_TITLE,
            character_id="narrator",
        )

        # Act / Assert
        assert segment.is_narratable

    def test_is_chapter_announcement_returns_true_for_chapter_announcement_type(self) -> None:
        """is_chapter_announcement() returns True only for CHAPTER_ANNOUNCEMENT segments."""
        # Arrange
        segment = Segment(
            text="Chapter Two. The Meeting.",
            segment_type=SegmentType.CHAPTER_ANNOUNCEMENT,
            character_id="narrator",
        )

        # Act / Assert
        assert segment.is_chapter_announcement()
        assert not segment.is_narration()
        assert not segment.is_dialogue()

    def test_is_chapter_announcement_returns_false_for_narration(self) -> None:
        """is_chapter_announcement() returns False for NARRATION segments."""
        # Arrange
        segment = Segment(text="She walked away.", segment_type=SegmentType.NARRATION)

        # Act / Assert
        assert not segment.is_chapter_announcement()


class TestBook:
    """Tests for Book model."""

    def test_to_dict_converts_book_to_dictionary(self):
        # Arrange
        section = Section(text="Once upon a time.")
        chapter = Chapter(number=1, title="Chapter I", sections=[section])
        metadata = BookMetadata(
            title="Test Book",
            author="Test Author",
            releaseDate="2020-01-01",
            language="en",
            originalPublication=None,
            credits=None
        )
        content = BookContent(chapters=[chapter])
        book = Book(metadata=metadata, content=content)

        # Act
        result = book.to_dict()

        # Assert
        assert isinstance(result, dict)
        assert result['metadata']['title'] == "Test Book"
        assert result['metadata']['author'] == "Test Author"
        assert result['metadata']['releaseDate'] == "2020-01-01"
        assert len(result['content']['chapters']) == 1
        assert result['content']['chapters'][0]['title'] == "Chapter I"

    def test_to_dict_converts_segment_types_to_strings(self):
        # Arrange
        segment = Segment(
            text="Hello",
            segment_type=SegmentType.DIALOGUE,
            character_id="john"
        )
        section = Section(text='"Hello"', segments=[segment])
        chapter = Chapter(number=1, title="Chapter I", sections=[section])
        metadata = BookMetadata(
            title="Test",
            author=None,
            releaseDate=None,
            language=None,
            originalPublication=None,
            credits=None
        )
        content = BookContent(chapters=[chapter])
        book = Book(metadata=metadata, content=content)

        # Act
        result = book.to_dict()

        # Assert
        segment_dict = result['content']['chapters'][0]['sections'][0]['segments'][0]  # noqa: E501
        assert segment_dict['segment_type'] == "dialogue"
        assert segment_dict['character_id'] == "john"

    def test_to_dict_handles_none_values(self):
        # Arrange
        section = Section(text="Test")
        chapter = Chapter(number=1, title="Chapter I", sections=[section])
        metadata = BookMetadata(
            title="Test",
            author=None,
            releaseDate=None,
            language=None,
            originalPublication=None,
            credits=None
        )
        content = BookContent(chapters=[chapter])
        book = Book(metadata=metadata, content=content)

        # Act
        result = book.to_dict()

        # Assert
        assert result['metadata']['author'] is None
        assert result['metadata']['releaseDate'] is None

    def test_to_dict_handles_sections_without_segments(self):
        # Arrange
        section = Section(text="Plain narration.")
        chapter = Chapter(number=1, title="Chapter I", sections=[section])
        metadata = BookMetadata(
            title="Test",
            author=None,
            releaseDate=None,
            language=None,
            originalPublication=None,
            credits=None
        )
        content = BookContent(chapters=[chapter])
        book = Book(metadata=metadata, content=content)

        # Act
        result = book.to_dict()

        # Assert
        section_dict = result['content']['chapters'][0]['sections'][0]
        assert section_dict['text'] == "Plain narration."
        assert section_dict['segments'] is None

    def test_to_dict_serializes_sound_effect_segments(self) -> None:
        """to_dict() correctly serializes SOUND_EFFECT segments with sound_effect_detail."""
        # Arrange
        sfx_segment = Segment(
            text="door knock",
            segment_type=SegmentType.SOUND_EFFECT,
            sound_effect_detail="4 firm knocks on a heavy old wooden door",
        )
        section = Section(text="A knock at the door.", segments=[sfx_segment])
        chapter = Chapter(number=1, title="Chapter I", sections=[section])
        metadata = BookMetadata(
            title="Test",
            author=None,
            releaseDate=None,
            language=None,
            originalPublication=None,
            credits=None,
        )
        content = BookContent(chapters=[chapter])
        book = Book(metadata=metadata, content=content)

        # Act
        result = book.to_dict()

        # Assert
        segment_dict = result['content']['chapters'][0]['sections'][0]['segments'][0]
        assert segment_dict['segment_type'] == "sound_effect"
        assert segment_dict['text'] == "door knock"
        assert segment_dict['sound_effect_detail'] == "4 firm knocks on a heavy old wooden door"
        assert segment_dict['character_id'] is None

    def test_vocal_effect_segment_round_trips_through_book_dict(self) -> None:
        """VOCAL_EFFECT segment survives a to_dict() / from_dict() round-trip."""
        # Arrange
        vocal_segment = Segment(
            text="soft breath intake",
            segment_type=SegmentType.VOCAL_EFFECT,
            character_id="alice",
        )
        section = Section(text="She inhaled softly.", segments=[vocal_segment])
        chapter = Chapter(number=1, title="Chapter I", sections=[section])
        metadata = BookMetadata(
            title="Test",
            author=None,
            releaseDate=None,
            language=None,
            originalPublication=None,
            credits=None,
        )
        content = BookContent(chapters=[chapter])
        book = Book(metadata=metadata, content=content)

        # Act
        restored = Book.from_dict(book.to_dict())

        # Assert
        segments = restored.content.chapters[0].sections[0].segments
        assert segments is not None
        seg = segments[0]
        assert seg.text == "soft breath intake"
        assert seg.segment_type == SegmentType.VOCAL_EFFECT
        assert seg.character_id == "alice"

    def test_from_dict_deserializes_sound_effect_segments(self) -> None:
        """from_dict() correctly reconstructs SOUND_EFFECT segments."""
        # Arrange
        data = {
            "metadata": {
                "title": "Test",
                "author": None,
                "releaseDate": None,
                "language": None,
                "originalPublication": None,
                "credits": None,
            },
            "content": {
                "chapters": [
                    {
                        "number": 1,
                        "title": "Chapter I",
                        "sections": [
                            {
                                "text": "A knock at the door.",
                                "segments": [
                                    {
                                        "text": "door knock",
                                        "segment_type": "sound_effect",
                                        "sound_effect_detail": "4 firm knocks on a heavy old wooden door",
                                        "character_id": None,
                                    }
                                ],
                                "section_type": None,
                            }
                        ],
                    }
                ]
            },
            "character_registry": [],
            "scene_registry": [],
        }

        # Act
        book = Book.from_dict(data)

        # Assert
        segments = book.content.chapters[0].sections[0].segments
        assert segments is not None
        segment = segments[0]
        assert segment.text == "door knock"
        assert segment.segment_type == SegmentType.SOUND_EFFECT
        assert segment.sound_effect_detail == "4 firm knocks on a heavy old wooden door"
        assert segment.character_id is None


# ── Character.to_dict / from_dict ─────────────────────────────────────────────

class TestCharacterToDictFromDict:
    """Tests for Character.to_dict() and Character.from_dict()."""

    def test_to_dict_returns_dict_with_all_keys(self) -> None:
        """to_dict() includes all Character fields."""
        # Arrange
        char = Character(character_id="harry", name="Harry Potter", sex="male", age="young")

        # Act
        result = char.to_dict()

        # Assert
        assert isinstance(result, dict)
        assert set(result.keys()) == {
            "character_id", "name", "description", "is_narrator",
            "sex", "age",
        }

    def test_to_dict_values_are_correct(self) -> None:
        """to_dict() returns correct values for all fields."""
        # Arrange
        char = Character(
            character_id="harry",
            name="Harry Potter",
            description="The chosen one",
            is_narrator=False,
            sex="male",
            age="young",
        )

        # Act
        result = char.to_dict()

        # Assert
        assert result["character_id"] == "harry"
        assert result["name"] == "Harry Potter"
        assert result["description"] == "The chosen one"
        assert result["is_narrator"] is False
        assert result["sex"] == "male"
        assert result["age"] == "young"

    def test_to_dict_none_fields_appear_as_none(self) -> None:
        """to_dict() preserves None for optional fields."""
        # Arrange
        char = Character(character_id="narrator", name="Narrator", is_narrator=True)

        # Act
        result = char.to_dict()

        # Assert
        assert result["description"] is None
        assert result["sex"] is None
        assert result["age"] is None

    def test_from_dict_constructs_character_with_all_fields(self) -> None:
        """from_dict() builds a Character from a complete dict."""
        # Arrange
        d = {
            "character_id": "hermione",
            "name": "Hermione Granger",
            "description": "Brilliant witch",
            "is_narrator": False,
            "sex": "female",
            "age": "young",
        }

        # Act
        char = Character.from_dict(d)

        # Assert
        assert char.character_id == "hermione"
        assert char.name == "Hermione Granger"
        assert char.description == "Brilliant witch"
        assert char.is_narrator is False
        assert char.sex == "female"
        assert char.age == "young"

    def test_from_dict_missing_sex_defaults_to_none(self) -> None:
        """from_dict() with no 'sex' key produces sex=None."""
        # Arrange
        d = {"character_id": "ron", "name": "Ron Weasley"}

        # Act
        char = Character.from_dict(d)

        # Assert
        assert char.sex is None

    def test_from_dict_missing_age_defaults_to_none(self) -> None:
        """from_dict() with no 'age' key produces age=None."""
        # Arrange
        d = {"character_id": "ron", "name": "Ron Weasley"}

        # Act
        char = Character.from_dict(d)

        # Assert
        assert char.age is None

    def test_from_dict_missing_description_defaults_to_none(self) -> None:
        """from_dict() with no 'description' key produces description=None."""
        # Arrange
        d = {"character_id": "ron", "name": "Ron Weasley"}

        # Act
        char = Character.from_dict(d)

        # Assert
        assert char.description is None

    def test_from_dict_missing_is_narrator_defaults_to_false(self) -> None:
        """from_dict() with no 'is_narrator' key produces is_narrator=False."""
        # Arrange
        d = {"character_id": "ron", "name": "Ron Weasley"}

        # Act
        char = Character.from_dict(d)

        # Assert
        assert char.is_narrator is False

    def test_round_trip_to_dict_from_dict(self) -> None:
        """to_dict() followed by from_dict() reconstructs the same Character."""
        # Arrange
        original = Character(
            character_id="dumbledore",
            name="Albus Dumbledore",
            description="Headmaster",
            is_narrator=False,
            sex="male",
            age="elderly",
        )

        # Act
        reconstructed = Character.from_dict(original.to_dict())

        # Assert
        assert reconstructed.character_id == original.character_id
        assert reconstructed.name == original.name
        assert reconstructed.description == original.description
        assert reconstructed.is_narrator == original.is_narrator
        assert reconstructed.sex == original.sex
        assert reconstructed.age == original.age


# ── CharacterRegistry ─────────────────────────────────────────────────────────

class TestCharacterRegistry:
    """Tests for CharacterRegistry."""

    def test_with_default_narrator_returns_registry_with_narrator(self) -> None:
        """with_default_narrator() bootstraps a registry with the narrator entry."""
        # Arrange — no setup required; factory method provides all inputs

        # Act
        registry = CharacterRegistry.with_default_narrator()

        # Assert
        assert len(registry.characters) == 1
        narrator = registry.characters[0]
        assert narrator.character_id == "narrator"
        assert narrator.is_narrator is True

    def test_with_default_narrator_narrator_name_is_set(self) -> None:
        """Narrator entry has a non-empty name."""
        # Arrange — no setup required; factory method provides all inputs

        # Act
        registry = CharacterRegistry.with_default_narrator()

        # Assert
        assert registry.characters[0].name  # non-empty string

    def test_get_returns_character_by_id(self) -> None:
        """get() finds a character by character_id."""
        # Arrange
        char = Character(character_id="harry", name="Harry Potter")
        registry = CharacterRegistry(characters=[char])

        # Act
        result = registry.get("harry")

        # Assert
        assert result is not None
        assert result.character_id == "harry"

    def test_get_returns_none_for_unknown_id(self) -> None:
        """get() returns None when character_id is not in registry."""
        # Arrange
        registry = CharacterRegistry()

        # Act / Assert
        assert registry.get("unknown") is None

    def test_add_inserts_character(self) -> None:
        """add() inserts a new character into the registry."""
        # Arrange
        registry = CharacterRegistry()
        char = Character(character_id="hermione", name="Hermione Granger")

        # Act
        registry.add(char)

        # Assert
        assert len(registry.characters) == 1
        assert registry.get("hermione") is not None

    def test_upsert_adds_new_character(self) -> None:
        """upsert() adds a character that does not yet exist."""
        # Arrange
        registry = CharacterRegistry()
        char = Character(character_id="ron", name="Ron Weasley")

        # Act
        registry.upsert(char)

        # Assert
        assert registry.get("ron") is not None

    def test_upsert_replaces_existing_character(self) -> None:
        """upsert() replaces an existing character with the same character_id."""
        # Arrange
        registry = CharacterRegistry()
        original = Character(character_id="dumbledore", name="Old man")
        registry.add(original)
        updated = Character(
            character_id="dumbledore",
            name="Albus Dumbledore",
            description="Wise and old"
        )

        # Act
        registry.upsert(updated)

        # Assert
        assert len(registry.characters) == 1
        found = registry.get("dumbledore")
        assert found is not None
        assert found.name == "Albus Dumbledore"
        assert found.description == "Wise and old"

    def test_upsert_does_not_duplicate(self) -> None:
        """Calling upsert twice for the same id results in exactly one entry."""
        # Arrange
        registry = CharacterRegistry()
        registry.upsert(Character(character_id="snape", name="Professor Snape"))

        # Act
        registry.upsert(Character(character_id="snape", name="Severus Snape"))

        # Assert
        assert len(registry.characters) == 1

    def test_get_narrator_from_default_registry(self) -> None:
        """get('narrator') works on a registry built with with_default_narrator()."""
        # Arrange
        registry = CharacterRegistry.with_default_narrator()

        # Act
        narrator = registry.get("narrator")

        # Assert
        assert narrator is not None
        assert narrator.is_narrator is True


# ── Book.character_registry field ─────────────────────────────────────────────

class TestBookCharacterRegistry:
    """Tests for the character_registry field on Book."""

    def _make_book(self, **kwargs) -> "Book":  # type: ignore[name-defined]
        section = Section(text="Test.")
        chapter = Chapter(number=1, title="Chapter I", sections=[section])
        metadata = BookMetadata(
            title="T", author=None, releaseDate=None,
            language=None, originalPublication=None, credits=None,
        )
        content = BookContent(chapters=[chapter])
        return Book(metadata=metadata, content=content, **kwargs)

    def test_book_default_character_registry_has_narrator(self) -> None:
        """Default character_registry contains the narrator character."""
        # Arrange — no setup required; helper builds a minimal valid book

        # Act
        book = self._make_book()

        # Assert
        assert book.character_registry.get("narrator") is not None

    def test_book_to_dict_includes_character_registry(self) -> None:
        """to_dict() must include a 'character_registry' key."""
        # Arrange
        book = self._make_book()

        # Act
        result = book.to_dict()

        # Assert
        assert "character_registry" in result

    def test_book_to_dict_character_registry_default_contains_narrator(self) -> None:
        """Default registry serialises to a list with one narrator entry."""
        # Arrange
        book = self._make_book()

        # Act
        result = book.to_dict()

        # Assert
        reg = result["character_registry"]
        assert len(reg) == 1
        assert reg[0]["character_id"] == "narrator"
        assert reg[0]["is_narrator"] is True

    def test_book_to_dict_character_registry_entry_has_all_keys(self) -> None:
        """Each entry in the serialised registry has all Character keys."""
        # Arrange
        book = self._make_book()

        # Act
        result = book.to_dict()

        # Assert
        entry = result["character_registry"][0]
        assert set(entry.keys()) == {
            "character_id", "name", "description", "is_narrator",
            "sex", "age",
        }

    def test_book_to_dict_character_registry_with_custom_characters(self) -> None:
        """Characters added to the registry appear in to_dict() output."""
        # Arrange
        registry = CharacterRegistry.with_default_narrator()
        char = Character(character_id="alice", name="Alice", sex="female", age="young")
        registry.add(char)
        book = self._make_book(character_registry=registry)

        # Act
        result = book.to_dict()

        # Assert
        reg = result["character_registry"]
        assert len(reg) == 2
        alice_entry = next(e for e in reg if e["character_id"] == "alice")
        assert alice_entry["name"] == "Alice"
        assert alice_entry["sex"] == "female"
        assert alice_entry["age"] == "young"


# ── Book.from_dict ─────────────────────────────────────────────────────────────

class TestBookFromDict:
    """Tests for Book.from_dict() round-trip."""

    def _make_book(self, **kwargs) -> "Book":  # type: ignore[name-defined]
        section = Section(text="Test.")
        chapter = Chapter(number=1, title="Chapter I", sections=[section])
        metadata = BookMetadata(
            title="T", author=None, releaseDate=None,
            language=None, originalPublication=None, credits=None,
        )
        content = BookContent(chapters=[chapter])
        return Book(metadata=metadata, content=content, **kwargs)

    def test_from_dict_restores_metadata_title(self) -> None:
        """from_dict() restores the book title."""
        # Arrange
        section = Section(text="Test.")
        chapter = Chapter(number=1, title="Chapter I", sections=[section])
        metadata = BookMetadata(
            title="Pride and Prejudice", author="Jane Austen",
            releaseDate="2000-01-01", language="en",
            originalPublication=None, credits=None,
        )
        book = Book(metadata=metadata, content=BookContent(chapters=[chapter]))

        # Act
        result = Book.from_dict(book.to_dict())

        # Assert
        assert result.metadata.title == "Pride and Prejudice"
        assert result.metadata.author == "Jane Austen"

    def test_from_dict_restores_character_registry(self) -> None:
        """from_dict() restores the character registry."""
        # Arrange
        registry = CharacterRegistry.with_default_narrator()
        char = Character(character_id="alice", name="Alice", sex="female", age="young")
        registry.add(char)
        book = self._make_book(character_registry=registry)

        # Act
        result = Book.from_dict(book.to_dict())

        # Assert
        assert isinstance(result.character_registry, CharacterRegistry)
        alice = result.character_registry.get("alice")
        assert alice is not None
        assert alice.name == "Alice"
        assert alice.sex == "female"
        assert alice.age == "young"

    def test_from_dict_restores_narrator_in_registry(self) -> None:
        """from_dict() preserves the narrator entry in the registry."""
        # Arrange
        book = self._make_book()

        # Act
        result = Book.from_dict(book.to_dict())

        # Assert
        narrator = result.character_registry.get("narrator")
        assert narrator is not None
        assert narrator.is_narrator is True

    def test_round_trip_preserves_chapter_count(self) -> None:
        """to_dict() -> from_dict() preserves chapter structure."""
        # Arrange
        book = self._make_book()

        # Act
        result = Book.from_dict(book.to_dict())

        # Assert
        assert len(result.content.chapters) == len(book.content.chapters)

    def test_round_trip_preserves_all_character_fields(self) -> None:
        """All six Character fields survive a to_dict / from_dict round-trip."""
        # Arrange
        registry = CharacterRegistry()
        original = Character(
            character_id="dumbledore",
            name="Albus Dumbledore",
            description="Headmaster",
            is_narrator=False,
            sex="male",
            age="elderly",
        )
        registry.add(original)
        book = self._make_book(character_registry=registry)

        # Act
        result = Book.from_dict(book.to_dict())

        # Assert
        restored = result.character_registry.get("dumbledore")
        assert restored is not None
        assert restored.character_id == original.character_id
        assert restored.name == original.name
        assert restored.description == original.description
        assert restored.is_narrator == original.is_narrator
        assert restored.sex == original.sex
        assert restored.age == original.age


# ── Section.section_type ──────────────────────────────────────────────────────


class TestSectionSectionType:
    """Tests for the section_type field on Section (US-007)."""

    def _make_book(self, section: "Section") -> "Book":  # type: ignore[name-defined]
        chapter = Chapter(number=1, title="Chapter I", sections=[section])
        metadata = BookMetadata(
            title="T", author=None, releaseDate=None,
            language=None, originalPublication=None, credits=None,
        )
        content = BookContent(chapters=[chapter])
        return Book(metadata=metadata, content=content)

    def test_book_to_dict_serialises_section_type_when_set(self) -> None:
        """Book.to_dict() includes section_type='illustration' for illustration sections."""
        # Arrange
        section = Section(text="Mr. & Mrs. Bennet", section_type="illustration")
        book = self._make_book(section)

        # Act
        result = book.to_dict()

        # Assert
        section_dict = result['content']['chapters'][0]['sections'][0]
        assert section_dict.get('section_type') == "illustration"

    def test_book_to_dict_serialises_section_type_none_when_not_set(self) -> None:
        """Book.to_dict() includes section_type=None for regular sections."""
        # Arrange
        section = Section(text="Normal paragraph.")
        book = self._make_book(section)

        # Act
        result = book.to_dict()

        # Assert
        section_dict = result['content']['chapters'][0]['sections'][0]
        assert 'section_type' in section_dict
        assert section_dict['section_type'] is None

    def test_book_from_dict_restores_section_type_illustration(self) -> None:
        """Book.from_dict() restores section_type='illustration' on sections."""
        # Arrange
        section = Section(text="Mr. & Mrs. Bennet", section_type="illustration")
        book = self._make_book(section)

        # Act
        restored = Book.from_dict(book.to_dict())

        # Assert
        restored_section = restored.content.chapters[0].sections[0]
        assert restored_section.section_type == "illustration"

    def test_book_from_dict_restores_section_type_none(self) -> None:
        """Book.from_dict() restores section_type=None on regular sections."""
        # Arrange
        section = Section(text="Normal paragraph.")
        book = self._make_book(section)

        # Act
        restored = Book.from_dict(book.to_dict())

        # Assert
        restored_section = restored.content.chapters[0].sections[0]
        assert restored_section.section_type is None


# ── Segment.emotion field ─────────────────────────────────────────────────────


class TestSegmentEmotionField:
    """Tests that Segment carries and serialises the emotion field (US-009)."""

    def _make_book_with_segment(self, segment: Segment) -> Book:
        section = Section(text="Test.", segments=[segment])
        chapter = Chapter(number=1, title="Chapter I", sections=[section])
        metadata = BookMetadata(
            title="T", author=None, releaseDate=None,
            language=None, originalPublication=None, credits=None,
        )
        return Book(metadata=metadata, content=BookContent(chapters=[chapter]))

    def test_segment_with_non_neutral_emotion_serialises_as_string(self) -> None:
        """to_dict() on a Book with emotion='angry' must yield 'emotion': 'angry' in segment dict."""
        # Arrange
        segment = Segment(
            text="I told you never to return!",
            segment_type=SegmentType.DIALOGUE,
            character_id="villain",
            emotion="angry",
        )
        book = self._make_book_with_segment(segment)

        # Act
        result = book.to_dict()

        # Assert
        seg_dict = result["content"]["chapters"][0]["sections"][0]["segments"][0]
        assert seg_dict["emotion"] == "angry"

    def test_segment_with_none_emotion_serialises_as_none(self) -> None:
        """to_dict() on a Book with emotion=None must yield 'emotion': None in segment dict."""
        # Arrange
        segment = Segment(
            text="She walked in.",
            segment_type=SegmentType.NARRATION,
            character_id="narrator",
            emotion=None,
        )
        book = self._make_book_with_segment(segment)

        # Act
        result = book.to_dict()

        # Assert
        seg_dict = result["content"]["chapters"][0]["sections"][0]["segments"][0]
        assert seg_dict["emotion"] is None

    def test_book_from_dict_restores_emotion_string(self) -> None:
        """Book.from_dict() round-trips emotion='stern' on Segment as plain string."""
        # Arrange
        segment = Segment(
            text="Indeed.",
            segment_type=SegmentType.DIALOGUE,
            character_id="mcgonagall",
            emotion="stern",
        )
        book = self._make_book_with_segment(segment)

        # Act
        restored = Book.from_dict(book.to_dict())

        # Assert
        restored_seg = restored.content.chapters[0].sections[0].segments[0]  # type: ignore[index]
        assert restored_seg.emotion == "stern"

    def test_book_from_dict_restores_none_emotion(self) -> None:
        """Book.from_dict() round-trips emotion=None on a segment correctly."""
        # Arrange
        segment = Segment(
            text="She walked away.",
            segment_type=SegmentType.NARRATION,
            character_id="narrator",
            emotion=None,
        )
        book = self._make_book_with_segment(segment)

        # Act
        restored = Book.from_dict(book.to_dict())

        # Assert
        restored_seg = restored.content.chapters[0].sections[0].segments[0]  # type: ignore[index]
        assert restored_seg.emotion is None

    def test_book_from_dict_accepts_legacy_uppercase_emotion_string(self) -> None:
        """Book.from_dict() accepts legacy uppercase emotion strings from old output.json files."""
        # Arrange — simulate an old serialised segment with uppercase emotion
        data = {
            "metadata": {
                "title": "T", "author": None, "releaseDate": None,
                "language": None, "originalPublication": None, "credits": None,
            },
            "content": {"chapters": [{
                "number": 1,
                "title": "Chapter I",
                "sections": [{
                    "text": "Rage!",
                    "segments": [{
                        "text": "Rage!",
                        "segment_type": "dialogue",
                        "character_id": "villain",
                        "emotion": "ANGRY",
                        "emphases": [],
                    }],
                    "emphases": [],
                    "section_type": None,
                }],
            }]},
            "character_registry": [],
        }

        # Act
        restored = Book.from_dict(data)

        # Assert — legacy uppercase string passes through unchanged
        restored_seg = restored.content.chapters[0].sections[0].segments[0]  # type: ignore[index]
        assert restored_seg.emotion == "ANGRY"


# ── Segment voice settings fields (US-019 Fix 3) ─────────────────────────────


class TestSegmentVoiceSettingsFields:
    """Tests that Segment carries and serialises voice_stability/style/speed."""

    def _make_book_with_segment(self, segment: Segment) -> Book:
        section = Section(text="Test.", segments=[segment])
        chapter = Chapter(number=1, title="Chapter I", sections=[section])
        metadata = BookMetadata(
            title="T", author=None, releaseDate=None,
            language=None, originalPublication=None, credits=None,
        )
        return Book(metadata=metadata, content=BookContent(chapters=[chapter]))

    def test_voice_settings_round_trip(self) -> None:
        """to_dict() → from_dict() preserves voice_stability/style/speed."""
        # Arrange
        segment = Segment(
            text="I WILL DESTROY YOU!",
            segment_type=SegmentType.DIALOGUE,
            character_id="villain",
            emotion="furious",
            voice_stability=0.25,
            voice_style=0.60,
            voice_speed=1.05,
        )
        book = self._make_book_with_segment(segment)

        # Act
        restored = Book.from_dict(book.to_dict())

        # Assert
        restored_seg = restored.content.chapters[0].sections[0].segments[0]  # type: ignore[index]
        assert restored_seg.voice_stability == 0.25
        assert restored_seg.voice_style == 0.60
        assert restored_seg.voice_speed == 1.05

    def test_legacy_segment_without_voice_settings_gets_none(self) -> None:
        """Book.from_dict() with a legacy segment dict missing voice settings yields None."""
        # Arrange
        data = {
            "metadata": {
                "title": "T", "author": None, "releaseDate": None,
                "language": None, "originalPublication": None, "credits": None,
            },
            "content": {"chapters": [{
                "number": 1,
                "title": "Chapter I",
                "sections": [{
                    "text": "Hello.",
                    "segments": [{
                        "text": "Hello.",
                        "segment_type": "dialogue",
                        "character_id": "alice",
                        "emotion": "neutral",
                    }],
                    "section_type": None,
                }],
            }]},
            "character_registry": [],
        }

        # Act
        restored = Book.from_dict(data)

        # Assert
        restored_seg = restored.content.chapters[0].sections[0].segments[0]  # type: ignore[index]
        assert restored_seg.voice_stability is None
        assert restored_seg.voice_style is None
        assert restored_seg.voice_speed is None


# ── Character.voice_design_prompt (US-014) ───────────────────────────────────


class TestCharacterVoiceDesignPrompt:
    """Tests for the voice_design_prompt derived property on Character (US-014)."""

    def test_derives_prompt_from_description_age_sex(self) -> None:
        """voice_design_prompt assembles '{age} {sex}, {description}.'."""
        # Arrange
        char = Character(
            character_id="hagrid",
            name="Rubeus Hagrid",
            sex="male",
            age="adult",
            description="booming bass voice, thick West Country accent",
        )

        # Act / Assert
        assert char.voice_design_prompt == "adult male, booming bass voice, thick West Country accent."

    def test_none_when_no_description(self) -> None:
        """voice_design_prompt is None when description is missing."""
        # Arrange
        char = Character(character_id="ron", name="Ron Weasley", sex="male", age="young")

        # Act / Assert
        assert char.voice_design_prompt is None

    def test_none_for_narrator(self) -> None:
        """voice_design_prompt is None for the narrator."""
        # Arrange
        char = Character(
            character_id="narrator",
            name="Narrator",
            is_narrator=True,
            description="calm authoritative voice",
        )

        # Act / Assert
        assert char.voice_design_prompt is None

    def test_strips_trailing_dot_from_description(self) -> None:
        """A description ending with '.' must not produce '..' in the prompt."""
        # Arrange
        char = Character(
            character_id="darcy",
            name="Mr Darcy",
            sex="male",
            age="adult",
            description="clipped aristocratic baritone.",
        )

        # Act / Assert
        assert char.voice_design_prompt == "adult male, clipped aristocratic baritone."


# ── Scene domain model (US-020) ──────────────────────────────────────────────


class TestSceneIsFrozen:
    """Scene is a value object -- frozen dataclass."""

    def test_scene_is_immutable(self) -> None:
        """Assigning to a field on a frozen Scene raises an error."""
        # Arrange
        scene = Scene(
            scene_id="ch1_cave",
            environment="cave",
            acoustic_hints=["echo", "confined"],
        )

        # Act / Assert
        import dataclasses
        with __import__("pytest").raises(dataclasses.FrozenInstanceError):
            scene.environment = "forest"  # type: ignore[misc]


# ── SceneRegistry ────────────────────────────────────────────────────────────


class TestSceneRegistryUpsert:
    """SceneRegistry.upsert adds new scenes and replaces existing ones."""

    def test_upsert_adds_new_scene(self) -> None:
        """Upserting a scene not in the registry adds it."""
        # Arrange
        registry = SceneRegistry()
        scene = Scene(scene_id="cave", environment="cave", acoustic_hints=["echo"])

        # Act
        registry.upsert(scene)

        # Assert
        assert registry.get("cave") is scene

    def test_upsert_replaces_existing_scene(self) -> None:
        """Upserting a scene with existing scene_id replaces the old one."""
        # Arrange
        registry = SceneRegistry()
        old_scene = Scene(scene_id="cave", environment="cave", acoustic_hints=["echo"])
        new_scene = Scene(scene_id="cave", environment="cave", acoustic_hints=["echo", "dripping"])
        registry.upsert(old_scene)

        # Act
        registry.upsert(new_scene)

        # Assert
        assert registry.get("cave") is new_scene
        assert len(registry.all()) == 1


class TestSceneRegistryGet:
    """SceneRegistry.get retrieves scenes by scene_id."""

    def test_get_returns_none_for_missing_scene(self) -> None:
        """get() returns None when scene_id is not in the registry."""
        # Arrange
        registry = SceneRegistry()

        # Act
        result = registry.get("nonexistent")

        # Assert
        assert result is None


class TestSceneRegistryAll:
    """SceneRegistry.all returns all scenes."""

    def test_all_returns_all_registered_scenes(self) -> None:
        """all() returns a list of all scenes in the registry."""
        # Arrange
        registry = SceneRegistry()
        scene1 = Scene(scene_id="cave", environment="cave")
        scene2 = Scene(scene_id="field", environment="outdoor_open")
        registry.upsert(scene1)
        registry.upsert(scene2)

        # Act
        result = registry.all()

        # Assert
        assert len(result) == 2
        scene_ids = {s.scene_id for s in result}
        assert scene_ids == {"cave", "field"}


class TestSceneRegistryToDictFromDict:
    """SceneRegistry serialization round-trip."""

    def test_to_dict_returns_list_of_scene_dicts(self) -> None:
        """to_dict() returns a list of scene dictionaries."""
        # Arrange
        registry = SceneRegistry()
        scene = Scene(
            scene_id="cave", environment="cave",
            acoustic_hints=["echo"], voice_modifiers={"stability_delta": -0.05},
        )
        registry.upsert(scene)

        # Act
        result = registry.to_dict()

        # Assert
        assert len(result) == 1
        assert result[0]["scene_id"] == "cave"
        assert result[0]["environment"] == "cave"
        assert result[0]["acoustic_hints"] == ["echo"]
        assert result[0]["voice_modifiers"] == {"stability_delta": -0.05}

    def test_from_dict_restores_scenes(self) -> None:
        """from_dict() reconstructs a SceneRegistry from a list of dicts."""
        # Arrange
        data = [
            {
                "scene_id": "cave",
                "environment": "cave",
                "acoustic_hints": ["echo"],
                "voice_modifiers": {"stability_delta": -0.05},
            },
            {
                "scene_id": "field",
                "environment": "outdoor_open",
                "acoustic_hints": [],
                "voice_modifiers": {},
            },
        ]

        # Act
        registry = SceneRegistry.from_dict(data)  # type: ignore[arg-type]

        # Assert
        assert len(registry.all()) == 2
        cave = registry.get("cave")
        assert cave is not None
        assert cave.environment == "cave"
        assert cave.voice_modifiers == {"stability_delta": -0.05}

    def test_round_trip_preserves_all_fields(self) -> None:
        """to_dict -> from_dict preserves all scene fields."""
        # Arrange
        registry = SceneRegistry()
        scene = Scene(
            scene_id="battle", environment="battlefield",
            acoustic_hints=["loud", "open"],
            voice_modifiers={"stability_delta": -0.10, "style_delta": 0.15, "speed": 1.10},
        )
        registry.upsert(scene)

        # Act
        restored = SceneRegistry.from_dict(registry.to_dict())

        # Assert
        restored_scene = restored.get("battle")
        assert restored_scene is not None
        assert restored_scene.environment == "battlefield"
        assert restored_scene.acoustic_hints == ["loud", "open"]
        assert restored_scene.voice_modifiers == {"stability_delta": -0.10, "style_delta": 0.15, "speed": 1.10}


# ── Segment.scene_id field ───────────────────────────────────────────────────


class TestSegmentSceneId:
    """Segment carries an optional scene_id referencing SceneRegistry."""

    def test_segment_scene_id_round_trips_through_book(self) -> None:
        """scene_id on a Segment survives Book.to_dict -> from_dict."""
        # Arrange
        segment = Segment(
            text="In the cave.",
            segment_type=SegmentType.NARRATION,
            character_id="narrator",
            scene_id="cave",
        )
        section = Section(text="In the cave.", segments=[segment])
        chapter = Chapter(number=1, title="Ch 1", sections=[section])
        metadata = BookMetadata(
            title="T", author=None, releaseDate=None,
            language=None, originalPublication=None, credits=None,
        )
        book = Book(metadata=metadata, content=BookContent(chapters=[chapter]))

        # Act
        restored = Book.from_dict(book.to_dict())

        # Assert
        restored_segs = restored.content.chapters[0].sections[0].segments
        assert restored_segs is not None
        assert restored_segs[0].scene_id == "cave"


# ── Book.scene_registry ─────────────────────────────────────────────────────


class TestBookSceneRegistry:
    """Book carries a SceneRegistry and serializes it."""

    def test_book_has_scene_registry(self) -> None:
        """Book has a scene_registry attribute that defaults to empty SceneRegistry."""
        # Arrange
        metadata = BookMetadata(
            title="T", author=None, releaseDate=None,
            language=None, originalPublication=None, credits=None,
        )
        book = Book(metadata=metadata, content=BookContent(chapters=[]))

        # Act / Assert
        assert len(book.scene_registry.all()) == 0

    def test_book_to_dict_includes_scene_registry(self) -> None:
        """Book.to_dict() includes scene_registry key."""
        # Arrange
        metadata = BookMetadata(
            title="T", author=None, releaseDate=None,
            language=None, originalPublication=None, credits=None,
        )
        registry = SceneRegistry()
        registry.upsert(Scene(scene_id="cave", environment="cave"))
        book = Book(
            metadata=metadata,
            content=BookContent(chapters=[]),
            scene_registry=registry,
        )

        # Act
        result = book.to_dict()

        # Assert
        assert "scene_registry" in result
        assert len(result["scene_registry"]) == 1
        assert result["scene_registry"][0]["scene_id"] == "cave"

    def test_book_from_dict_restores_scene_registry(self) -> None:
        """Book.from_dict() restores the scene_registry."""
        # Arrange
        metadata = BookMetadata(
            title="T", author=None, releaseDate=None,
            language=None, originalPublication=None, credits=None,
        )
        scene_registry = SceneRegistry()
        scene_registry.upsert(
            Scene(scene_id="cave", environment="cave", acoustic_hints=["echo"],
                  voice_modifiers={"stability_delta": -0.05})
        )
        book = Book(
            metadata=metadata,
            content=BookContent(chapters=[]),
            scene_registry=scene_registry,
        )

        # Act
        restored = Book.from_dict(book.to_dict())

        # Assert
        cave = restored.scene_registry.get("cave")
        assert cave is not None
        assert cave.environment == "cave"
        assert cave.voice_modifiers == {"stability_delta": -0.05}

    def test_book_from_dict_legacy_data_without_scene_registry(self) -> None:
        """Book.from_dict() handles legacy data without scene_registry key."""
        # Arrange
        data = {
            "metadata": {
                "title": "T", "author": None, "releaseDate": None,
                "language": None, "originalPublication": None, "credits": None,
            },
            "content": {"chapters": []},
            "character_registry": [],
            # No "scene_registry" key
        }

        # Act
        restored = Book.from_dict(data)

        # Assert
        assert len(restored.scene_registry.all()) == 0


# ── US-011: Scene ambient fields ─────────────────────────────────────────────


class TestSceneAmbientFieldsRoundTrip:
    """Scene.ambient_prompt and ambient_volume survive serialization round-trips."""

    def test_scene_ambient_fields_round_trip_through_registry(self) -> None:
        """ambient_prompt and ambient_volume survive SceneRegistry to_dict -> from_dict."""
        # Arrange
        registry = SceneRegistry()
        scene = Scene(
            scene_id="drawing_room",
            environment="indoor_quiet",
            acoustic_hints=["warm"],
            voice_modifiers={},
            ambient_prompt="quiet drawing room, clock ticking, distant servant footsteps",
            ambient_volume=-18.0,
        )
        registry.upsert(scene)

        # Act
        restored = SceneRegistry.from_dict(registry.to_dict())

        # Assert
        restored_scene = restored.get("drawing_room")
        assert restored_scene is not None
        assert restored_scene.ambient_prompt == "quiet drawing room, clock ticking, distant servant footsteps"
        assert restored_scene.ambient_volume == -18.0

    def test_scene_ambient_none_round_trips_through_registry(self) -> None:
        """Scene with ambient_prompt=None survives to_dict -> from_dict as None."""
        # Arrange
        registry = SceneRegistry()
        scene = Scene(scene_id="bare", environment="indoor_quiet")
        registry.upsert(scene)

        # Act
        restored = SceneRegistry.from_dict(registry.to_dict())

        # Assert
        restored_scene = restored.get("bare")
        assert restored_scene is not None
        assert restored_scene.ambient_prompt is None
        assert restored_scene.ambient_volume is None

    def test_book_round_trip_preserves_ambient_fields(self) -> None:
        """ambient_prompt/ambient_volume survive Book.to_dict -> from_dict."""
        # Arrange
        metadata = BookMetadata(
            title="T", author=None, releaseDate=None,
            language=None, originalPublication=None, credits=None,
        )
        scene_registry = SceneRegistry()
        scene_registry.upsert(Scene(
            scene_id="battlefield",
            environment="battlefield",
            ambient_prompt="clashing swords, war cries, thundering hooves",
            ambient_volume=-16.0,
        ))
        book = Book(
            metadata=metadata,
            content=BookContent(chapters=[]),
            scene_registry=scene_registry,
        )

        # Act
        restored = Book.from_dict(book.to_dict())

        # Assert
        battle = restored.scene_registry.get("battlefield")
        assert battle is not None
        assert battle.ambient_prompt == "clashing swords, war cries, thundering hooves"
        assert battle.ambient_volume == -16.0


# ── Segment.sound_effect_description field ────────────────────────────────



# ── TD-008: AIPrompt structured model ────────────────────────────────────────


class TestAIPromptConstruction:
    """Tests for AIPrompt frozen dataclass construction."""

    def test_frozen_dataclass_cannot_be_mutated(self) -> None:
        """AIPrompt is frozen and cannot be mutated after construction."""
        # Arrange
        prompt = AIPrompt(
            static_instructions="static",
            book_context="book",
            character_registry="registry",
            surrounding_context="context",
            scene_registry="scenes",
            text_to_segment="text",
        )

        # Act & Assert
        with pytest.raises(FrozenInstanceError):
            prompt.static_instructions = "modified"  # type: ignore[misc]


class TestAIPromptBuildStaticPortion:
    """Tests for AIPrompt.build_static_portion() method."""

    def test_build_static_portion_concatenates_static_and_book(self) -> None:
        """build_static_portion returns static_instructions + book_context."""
        # Arrange
        prompt = AIPrompt(
            static_instructions="RULES:",
            book_context="Book: Pride and Prejudice",
            character_registry="ignored",
            surrounding_context="ignored",
            scene_registry="ignored",
            text_to_segment="ignored",
        )

        # Act
        result = prompt.build_static_portion()

        # Assert
        assert result == "RULES:Book: Pride and Prejudice"

    def test_build_static_portion_with_empty_fields(self) -> None:
        """build_static_portion works with empty strings."""
        # Arrange
        prompt = AIPrompt(
            static_instructions="",
            book_context="",
            character_registry="x",
            surrounding_context="y",
            scene_registry="z",
            text_to_segment="w",
        )

        # Act
        result = prompt.build_static_portion()

        # Assert
        assert result == ""

    def test_build_static_portion_with_only_static(self) -> None:
        """build_static_portion works when book_context is empty."""
        # Arrange
        prompt = AIPrompt(
            static_instructions="STATIC",
            book_context="",
            character_registry="x",
            surrounding_context="y",
            scene_registry="z",
            text_to_segment="w",
        )

        # Act
        result = prompt.build_static_portion()

        # Assert
        assert result == "STATIC"

    def test_build_static_portion_with_only_book(self) -> None:
        """build_static_portion works when static_instructions is empty."""
        # Arrange
        prompt = AIPrompt(
            static_instructions="",
            book_context="BOOK",
            character_registry="x",
            surrounding_context="y",
            scene_registry="z",
            text_to_segment="w",
        )

        # Act
        result = prompt.build_static_portion()

        # Assert
        assert result == "BOOK"


class TestAIPromptBuildDynamicPortion:
    """Tests for AIPrompt.build_dynamic_portion() method."""

    def test_build_dynamic_portion_concatenates_four_fields(self) -> None:
        """build_dynamic_portion returns registry + context + scenes + text."""
        # Arrange
        prompt = AIPrompt(
            static_instructions="ignored",
            book_context="ignored",
            character_registry="REGISTRY:",
            surrounding_context="CONTEXT:",
            scene_registry="SCENES:",
            text_to_segment="TEXT TO PARSE",
        )

        # Act
        result = prompt.build_dynamic_portion()

        # Assert
        assert result == "REGISTRY:CONTEXT:SCENES:TEXT TO PARSE"

    def test_build_dynamic_portion_with_empty_fields(self) -> None:
        """build_dynamic_portion works with empty strings."""
        # Arrange
        prompt = AIPrompt(
            static_instructions="a",
            book_context="b",
            character_registry="",
            surrounding_context="",
            scene_registry="",
            text_to_segment="",
        )

        # Act
        result = prompt.build_dynamic_portion()

        # Assert
        assert result == ""

    def test_build_dynamic_portion_with_partial_fields(self) -> None:
        """build_dynamic_portion concatenates whatever is provided."""
        # Arrange
        prompt = AIPrompt(
            static_instructions="x",
            book_context="y",
            character_registry="CHAR",
            surrounding_context="",
            scene_registry="",
            text_to_segment="TEXT",
        )

        # Act
        result = prompt.build_dynamic_portion()

        # Assert
        assert result == "CHARTEXT"


class TestAIPromptBuildFullPrompt:
    """Tests for AIPrompt.build_full_prompt() method."""

    def test_build_full_prompt_returns_complete_concatenation(self) -> None:
        """build_full_prompt returns all 6 fields concatenated in order."""
        # Arrange
        prompt = AIPrompt(
            static_instructions="STATIC1",
            book_context="BOOK1",
            character_registry="CHAR1",
            surrounding_context="CTX1",
            scene_registry="SCENE1",
            text_to_segment="TEXT1",
        )

        # Act
        result = prompt.build_full_prompt()

        # Assert
        # Should be: static + book + char + ctx + scene + text
        assert result == "STATIC1BOOK1CHAR1CTX1SCENE1TEXT1"

    def test_build_full_prompt_with_multiline_fields(self) -> None:
        """build_full_prompt preserves multiline content."""
        # Arrange
        prompt = AIPrompt(
            static_instructions="STATIC\nLine 2",
            book_context="\nBOOK",
            character_registry="CHAR\n",
            surrounding_context="\nCTX\n",
            scene_registry="SCENE",
            text_to_segment="\nTEXT",
        )

        # Act
        result = prompt.build_full_prompt()

        # Assert
        expected = "STATIC\nLine 2\nBOOKCHAR\n\nCTX\nSCENE\nTEXT"
        assert result == expected

    def test_build_full_prompt_with_empty_fields(self) -> None:
        """build_full_prompt works with all empty strings."""
        # Arrange
        prompt = AIPrompt(
            static_instructions="",
            book_context="",
            character_registry="",
            surrounding_context="",
            scene_registry="",
            text_to_segment="",
        )

        # Act
        result = prompt.build_full_prompt()

        # Assert
        assert result == ""

    def test_build_full_prompt_equals_static_plus_dynamic(self) -> None:
        """build_full_prompt() should equal build_static_portion() + build_dynamic_portion()."""
        # Arrange
        prompt = AIPrompt(
            static_instructions="S",
            book_context="B",
            character_registry="C",
            surrounding_context="X",
            scene_registry="E",
            text_to_segment="T",
        )

        # Act
        full = prompt.build_full_prompt()
        static = prompt.build_static_portion()
        dynamic = prompt.build_dynamic_portion()

        # Assert
        assert full == static + dynamic


class TestAIPromptBuildMethodsConsistency:
    """Tests that builder methods are idempotent and consistent."""

    def test_build_methods_are_idempotent(self) -> None:
        """Calling build methods multiple times returns consistent results."""
        # Arrange
        prompt = AIPrompt(
            static_instructions="S",
            book_context="B",
            character_registry="C",
            surrounding_context="X",
            scene_registry="E",
            text_to_segment="T",
        )

        # Act & Assert
        assert prompt.build_static_portion() == "SB"
        assert prompt.build_static_portion() == "SB"
        assert prompt.build_dynamic_portion() == "CXET"
        assert prompt.build_dynamic_portion() == "CXET"
        assert prompt.build_full_prompt() == "SBCXET"
        assert prompt.build_full_prompt() == "SBCXET"

    def test_build_methods_do_not_modify_prompt(self) -> None:
        """Calling build methods does not modify the frozen prompt."""
        # Arrange
        prompt = AIPrompt(
            static_instructions="S",
            book_context="B",
            character_registry="C",
            surrounding_context="X",
            scene_registry="E",
            text_to_segment="T",
        )
        static_before = prompt.static_instructions

        # Act
        _ = prompt.build_static_portion()
        _ = prompt.build_dynamic_portion()
        _ = prompt.build_full_prompt()

        # Assert (fields unchanged)
        assert prompt.static_instructions == static_before


# ── US-033: Audio path and timing fields ────────────────────────────────────


class TestSegmentAudioFields:
    """Tests for Segment audio_path and duration_seconds fields."""

    def test_segment_audio_path_can_be_set(self) -> None:
        """Segment.audio_path can store a file path."""
        # Arrange
        segment = Segment(
            text="Hello",
            segment_type=SegmentType.NARRATION,
            audio_path="/path/to/audio.mp3",
        )

        # Act
        result = segment.audio_path

        # Assert
        assert result == "/path/to/audio.mp3"

    def test_segment_duration_seconds_can_be_set(self) -> None:
        """Segment.duration_seconds can store a float duration."""
        # Arrange
        segment = Segment(
            text="Hello",
            segment_type=SegmentType.NARRATION,
            duration_seconds=3.5,
        )

        # Act
        result = segment.duration_seconds

        # Assert
        assert result == 3.5


class TestChapterAudioPathsFields:
    """Tests for Chapter ambient/sfx/music audio path lists."""

    def test_chapter_ambient_audio_paths_can_store_list(self) -> None:
        """Chapter.ambient_audio_paths stores list of paths."""
        # Arrange
        paths = ["/path/to/ambient1.mp3", "/path/to/ambient2.mp3"]
        chapter = Chapter(
            number=1,
            title="Test",
            sections=[],
            ambient_audio_paths=paths,
        )

        # Act
        result = chapter.ambient_audio_paths

        # Assert
        assert result == paths

    def test_chapter_sfx_audio_paths_can_store_list(self) -> None:
        """Chapter.sfx_audio_paths stores list of paths."""
        # Arrange
        paths = ["/path/to/sfx1.mp3"]
        chapter = Chapter(
            number=1,
            title="Test",
            sections=[],
            sfx_audio_paths=paths,
        )

        # Act
        result = chapter.sfx_audio_paths

        # Assert
        assert result == paths

    def test_chapter_music_audio_paths_can_store_list(self) -> None:
        """Chapter.music_audio_paths stores list of paths."""
        # Arrange
        paths = ["/path/to/music1.mp3", "/path/to/music2.mp3", "/path/to/music3.mp3"]
        chapter = Chapter(
            number=1,
            title="Test",
            sections=[],
            music_audio_paths=paths,
        )

        # Act
        result = chapter.music_audio_paths

        # Assert
        assert result == paths


class TestBookSerializationWithAudioFields:
    """Tests for Book.to_dict() and Book.from_dict() with new audio fields."""

    def test_book_to_dict_includes_segment_audio_path(self) -> None:
        """Book.to_dict() serializes Segment.audio_path."""
        # Arrange
        segment = Segment(
            text="Test",
            segment_type=SegmentType.DIALOGUE,
            character_id="alice",
            audio_path="/audio/seg1.mp3",
            duration_seconds=2.3,
        )
        section = Section(text="Test", segments=[segment])
        chapter = Chapter(number=1, title="Ch1", sections=[section])
        content = BookContent(chapters=[chapter])
        metadata = BookMetadata(
            title="Test Book",
            author="Test Author",
            releaseDate=None,
            language=None,
            originalPublication=None,
            credits=None,
        )
        book = Book(metadata=metadata, content=content)

        # Act
        data = book.to_dict()

        # Assert
        seg_data = data["content"]["chapters"][0]["sections"][0]["segments"][0]
        assert seg_data["audio_path"] == "/audio/seg1.mp3"
        assert seg_data["duration_seconds"] == 2.3

    def test_book_to_dict_includes_chapter_audio_paths(self) -> None:
        """Book.to_dict() serializes Chapter ambient/sfx/music paths."""
        # Arrange
        chapter = Chapter(
            number=1,
            title="Ch1",
            sections=[],
            ambient_audio_paths=["/ambient/a1.mp3"],
            sfx_audio_paths=["/sfx/s1.mp3", "/sfx/s2.mp3"],
            music_audio_paths=["/music/m1.mp3"],
        )
        content = BookContent(chapters=[chapter])
        metadata = BookMetadata(
            title="Test Book",
            author=None,
            releaseDate=None,
            language=None,
            originalPublication=None,
            credits=None,
        )
        book = Book(metadata=metadata, content=content)

        # Act
        data = book.to_dict()

        # Assert
        ch_data = data["content"]["chapters"][0]
        assert ch_data["ambient_audio_paths"] == ["/ambient/a1.mp3"]
        assert ch_data["sfx_audio_paths"] == ["/sfx/s1.mp3", "/sfx/s2.mp3"]
        assert ch_data["music_audio_paths"] == ["/music/m1.mp3"]

    def test_book_from_dict_restores_segment_audio_fields(self) -> None:
        """Book.from_dict() deserializes Segment audio_path and duration_seconds."""
        # Arrange
        data = {
            "metadata": {
                "title": "Test",
                "author": None,
                "releaseDate": None,
                "language": None,
                "originalPublication": None,
                "credits": None,
            },
            "content": {
                "chapters": [
                    {
                        "number": 1,
                        "title": "Chapter One",
                        "sections": [
                            {
                                "text": "Section text",
                                "segments": [
                                    {
                                        "text": "Dialogue text",
                                        "segment_type": "dialogue",
                                        "character_id": "bob",
                                        "audio_path": "/restored/audio.mp3",
                                        "duration_seconds": 4.7,
                                    }
                                ],
                            }
                        ],
                    }
                ]
            },
            "character_registry": [],
            "scene_registry": [],
        }

        # Act
        book = Book.from_dict(data)

        # Assert
        segment = book.content.chapters[0].sections[0].segments[0]  # type: ignore[index]
        assert segment.audio_path == "/restored/audio.mp3"
        assert segment.duration_seconds == 4.7

    def test_book_from_dict_restores_chapter_audio_paths(self) -> None:
        """Book.from_dict() deserializes Chapter ambient/sfx/music paths."""
        # Arrange
        data = {
            "metadata": {
                "title": "Test",
                "author": None,
                "releaseDate": None,
                "language": None,
                "originalPublication": None,
                "credits": None,
            },
            "content": {
                "chapters": [
                    {
                        "number": 1,
                        "title": "Chapter One",
                        "sections": [],
                        "ambient_audio_paths": ["/restored/amb1.mp3", "/restored/amb2.mp3"],
                        "sfx_audio_paths": ["/restored/sfx1.mp3"],
                        "music_audio_paths": [],
                    }
                ]
            },
            "character_registry": [],
            "scene_registry": [],
        }

        # Act
        book = Book.from_dict(data)

        # Assert
        chapter = book.content.chapters[0]
        assert chapter.ambient_audio_paths == ["/restored/amb1.mp3", "/restored/amb2.mp3"]
        assert chapter.sfx_audio_paths == ["/restored/sfx1.mp3"]
        assert chapter.music_audio_paths == []
