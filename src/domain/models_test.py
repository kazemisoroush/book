"""Tests for domain models."""
from .models import (
    Segment, SegmentType, Section, Chapter, Book, BookMetadata, BookContent,
    EmphasisSpan, Character, CharacterRegistry,
)


class TestSegment:
    """Tests for Segment model."""

    def test_segment_has_no_speaker_field(self) -> None:
        """Segment must not have a 'speaker' field after the rename."""
        # Arrange
        segment = Segment(text="test", segment_type=SegmentType.NARRATION)

        # Assert
        assert not hasattr(segment, "speaker")

    def test_is_illustration_returns_true_for_illustration_type(self) -> None:
        """is_illustration() returns True for ILLUSTRATION segment type."""
        # Arrange
        segment = Segment(text="[Illustration]", segment_type=SegmentType.ILLUSTRATION)

        # Assert
        assert segment.is_illustration()
        assert not segment.is_narration()
        assert not segment.is_dialogue()

    def test_is_copyright_returns_true_for_copyright_type(self) -> None:
        """is_copyright() returns True for COPYRIGHT segment type."""
        # Arrange
        segment = Segment(text="Copyright 2020", segment_type=SegmentType.COPYRIGHT)

        # Assert
        assert segment.is_copyright()
        assert not segment.is_narration()

    def test_is_other_returns_true_for_other_type(self) -> None:
        """is_other() returns True for OTHER segment type."""
        # Arrange
        segment = Segment(text="{6}", segment_type=SegmentType.OTHER)

        # Assert
        assert segment.is_other()
        assert not segment.is_narration()


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


# ── Section.emphases ──────────────────────────────────────────────────────────

class TestSectionEmphases:
    """Tests for the emphases field on Section."""

    def test_section_emphases_are_independent_across_instances(self) -> None:
        """Two Section instances do not share the same emphases list."""
        # Arrange
        s1 = Section(text="A")
        s2 = Section(text="B")

        # Act
        s1.emphases.append(EmphasisSpan(start=0, end=1, kind="b"))

        # Assert
        assert s2.emphases == []


# ── to_dict serialisation of emphases ─────────────────────────────────────────

class TestToDictWithEmphases:
    """Tests that Book.to_dict() serialises EmphasisSpan correctly."""

    def test_to_dict_serialises_section_emphases(self) -> None:
        """emphases list on Section appears in to_dict output."""
        # Arrange
        span = EmphasisSpan(start=0, end=5, kind="em")
        section = Section(text="Hello world.", emphases=[span])
        chapter = Chapter(number=1, title="Chapter I", sections=[section])
        metadata = BookMetadata(
            title="T", author=None, releaseDate=None,
            language=None, originalPublication=None, credits=None,
        )
        book = Book(metadata=metadata, content=BookContent(chapters=[chapter]))

        # Act
        result = book.to_dict()

        # Assert
        section_dict = result['content']['chapters'][0]['sections'][0]
        assert 'emphases' in section_dict
        assert len(section_dict['emphases']) == 1
        assert section_dict['emphases'][0]['start'] == 0
        assert section_dict['emphases'][0]['end'] == 5
        assert section_dict['emphases'][0]['kind'] == "em"

    def test_to_dict_serialises_empty_emphases_as_empty_list(self) -> None:
        """Section with no emphasis spans serialises as an empty list."""
        # Arrange
        section = Section(text="Plain.")
        chapter = Chapter(number=1, title="Chapter I", sections=[section])
        metadata = BookMetadata(
            title="T", author=None, releaseDate=None,
            language=None, originalPublication=None, credits=None,
        )
        book = Book(metadata=metadata, content=BookContent(chapters=[chapter]))

        # Act
        result = book.to_dict()

        # Assert
        section_dict = result['content']['chapters'][0]['sections'][0]
        assert section_dict['emphases'] == []


# ── Character.to_dict / from_dict ─────────────────────────────────────────────

class TestCharacterToDictFromDict:
    """Tests for Character.to_dict() and Character.from_dict()."""

    def test_to_dict_returns_dict_with_all_six_keys(self) -> None:
        """to_dict() includes character_id, name, description, is_narrator, sex, age."""
        # Arrange
        char = Character(character_id="harry", name="Harry Potter", sex="male", age="young")

        # Act
        result = char.to_dict()

        # Assert
        assert isinstance(result, dict)
        assert set(result.keys()) == {"character_id", "name", "description", "is_narrator", "sex", "age"}

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
        # Act
        registry = CharacterRegistry.with_default_narrator()

        # Assert
        assert len(registry.characters) == 1
        narrator = registry.characters[0]
        assert narrator.character_id == "narrator"
        assert narrator.is_narrator is True

    def test_with_default_narrator_narrator_name_is_set(self) -> None:
        """Narrator entry has a non-empty name."""
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

        # Assert
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

    def test_book_to_dict_character_registry_is_a_list(self) -> None:
        """to_dict()['character_registry'] must be a list."""
        # Arrange
        book = self._make_book()

        # Act
        result = book.to_dict()

        # Assert
        assert isinstance(result["character_registry"], list)

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
        """Each entry in the serialised registry has all six Character keys."""
        # Arrange
        book = self._make_book()

        # Act
        result = book.to_dict()

        # Assert
        entry = result["character_registry"][0]
        assert set(entry.keys()) == {"character_id", "name", "description", "is_narrator", "sex", "age"}

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

    def test_from_dict_returns_book_instance(self) -> None:
        """Book.from_dict() returns a Book."""
        # Arrange
        book = self._make_book()

        # Act
        result = Book.from_dict(book.to_dict())

        # Assert
        assert isinstance(result, Book)

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
