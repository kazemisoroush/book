"""Tests for domain models."""
from .models import (
    Segment, SegmentType, Section, Chapter, Book, BookMetadata, BookContent,
    EmphasisSpan, Character, CharacterRegistry,
)


class TestSegment:
    """Tests for Segment model."""

    def test_create_narration_segment(self):
        segment = Segment(
            text="It was a dark and stormy night.",
            segment_type=SegmentType.NARRATION
        )

        assert segment.text == "It was a dark and stormy night."
        assert segment.is_narration()
        assert not segment.is_dialogue()
        assert segment.character_id is None

    def test_create_dialogue_segment(self):
        segment = Segment(
            text="Hello, how are you?",
            segment_type=SegmentType.DIALOGUE,
            character_id="john"
        )

        assert segment.text == "Hello, how are you?"
        assert segment.is_dialogue()
        assert not segment.is_narration()
        assert segment.character_id == "john"

    def test_segment_has_no_speaker_field(self) -> None:
        """Segment must not have a 'speaker' field after the rename."""
        segment = Segment(text="test", segment_type=SegmentType.NARRATION)
        assert not hasattr(segment, "speaker")

    def test_is_illustration_returns_true_for_illustration_type(self) -> None:
        """is_illustration() returns True for ILLUSTRATION segment type."""
        segment = Segment(text="[Illustration]", segment_type=SegmentType.ILLUSTRATION)
        assert segment.is_illustration()
        assert not segment.is_narration()
        assert not segment.is_dialogue()

    def test_is_copyright_returns_true_for_copyright_type(self) -> None:
        """is_copyright() returns True for COPYRIGHT segment type."""
        segment = Segment(text="Copyright 2020", segment_type=SegmentType.COPYRIGHT)
        assert segment.is_copyright()
        assert not segment.is_narration()

    def test_is_other_returns_true_for_other_type(self) -> None:
        """is_other() returns True for OTHER segment type."""
        segment = Segment(text="{6}", segment_type=SegmentType.OTHER)
        assert segment.is_other()
        assert not segment.is_narration()


class TestSection:
    """Tests for Section model."""

    def test_create_section_without_segments(self):
        """Test section with just text (plain narration paragraph)."""
        section = Section(text="It was a beautiful day.")

        assert section.text == "It was a beautiful day."
        assert section.segments is None

    def test_create_section_with_segments(self):
        """Test section with dialogue breakdown into segments."""
        segment1 = Segment(
            text="Hello there,",
            segment_type=SegmentType.DIALOGUE,
            character_id="john"
        )
        segment2 = Segment(
            text="said John.",
            segment_type=SegmentType.NARRATION
        )

        section = Section(
            text='"Hello there," said John.',
            segments=[segment1, segment2]
        )

        assert section.text == '"Hello there," said John.'
        assert section.segments is not None
        assert len(section.segments) == 2
        assert section.segments[0].is_dialogue()
        assert section.segments[1].is_narration()


class TestChapter:
    """Tests for Chapter model."""

    def test_create_chapter(self):
        """Test chapter contains sections (paragraphs)."""
        section1 = Section(text="It was a dark night.")
        section2 = Section(text="The wind howled.")

        chapter = Chapter(
            number=1,
            title="Chapter I",
            sections=[section1, section2]
        )

        assert chapter.number == 1
        assert chapter.title == "Chapter I"
        assert len(chapter.sections) == 2


class TestBook:
    """Tests for Book model."""

    def test_create_book(self):
        section = Section(text="Once upon a time.")
        chapter = Chapter(number=1, title="Chapter I", sections=[section])
        metadata = BookMetadata(
            title="Test Book",
            author="Test Author",
            releaseDate=None,
            language=None,
            originalPublication=None,
            credits=None
        )
        content = BookContent(chapters=[chapter])
        book = Book(metadata=metadata, content=content)

        assert book.metadata.title == "Test Book"
        assert book.metadata.author == "Test Author"
        assert len(book.content.chapters) == 1

    def test_to_dict_converts_book_to_dictionary(self):
        # Given
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

        # When
        result = book.to_dict()

        # Then
        assert isinstance(result, dict)
        assert result['metadata']['title'] == "Test Book"
        assert result['metadata']['author'] == "Test Author"
        assert result['metadata']['releaseDate'] == "2020-01-01"
        assert len(result['content']['chapters']) == 1
        assert result['content']['chapters'][0]['title'] == "Chapter I"

    def test_to_dict_converts_segment_types_to_strings(self):
        # Given
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

        # When
        result = book.to_dict()

        # Then
        segment_dict = result['content']['chapters'][0]['sections'][0]['segments'][0]  # noqa: E501
        assert segment_dict['segment_type'] == "dialogue"
        assert segment_dict['character_id'] == "john"

    def test_to_dict_handles_none_values(self):
        # Given
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

        # When
        result = book.to_dict()

        # Then
        assert result['metadata']['author'] is None
        assert result['metadata']['releaseDate'] is None

    def test_to_dict_handles_sections_without_segments(self):
        # Given
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

        # When
        result = book.to_dict()

        # Then
        section_dict = result['content']['chapters'][0]['sections'][0]
        assert section_dict['text'] == "Plain narration."
        assert section_dict['segments'] is None


# ── EmphasisSpan ──────────────────────────────────────────────────────────────

class TestEmphasisSpan:
    """Tests for EmphasisSpan model."""

    def test_create_emphasis_span_with_all_fields(self) -> None:
        """EmphasisSpan stores start, end, and kind correctly."""
        span = EmphasisSpan(start=4, end=9, kind="em")
        assert span.start == 4
        assert span.end == 9
        assert span.kind == "em"

    def test_emphasis_span_accepts_all_inline_tag_kinds(self) -> None:
        """EmphasisSpan accepts each expected inline tag name."""
        for kind in ("em", "b", "strong", "i"):
            span = EmphasisSpan(start=0, end=5, kind=kind)
            assert span.kind == kind

    def test_emphasis_span_zero_width_is_valid(self) -> None:
        """EmphasisSpan with start == end is structurally valid."""
        span = EmphasisSpan(start=3, end=3, kind="em")
        assert span.start == span.end


# ── Section.emphases ──────────────────────────────────────────────────────────

class TestSectionEmphases:
    """Tests for the emphases field on Section."""

    def test_section_emphases_defaults_to_empty_list(self) -> None:
        """Section created without emphases has an empty list, not None."""
        section = Section(text="Hello world.")
        assert section.emphases == []

    def test_section_emphases_accepts_span_list(self) -> None:
        """Section stores a list of EmphasisSpan objects."""
        span = EmphasisSpan(start=0, end=5, kind="em")
        section = Section(text="Hello world.", emphases=[span])
        assert len(section.emphases) == 1
        assert section.emphases[0].kind == "em"

    def test_section_existing_construction_still_works(self) -> None:
        """Section(text=...) without emphases keyword still works."""
        section = Section(text="Plain text.")
        assert section.text == "Plain text."
        assert section.segments is None
        assert section.emphases == []

    def test_section_emphases_are_independent_across_instances(self) -> None:
        """Two Section instances do not share the same emphases list."""
        s1 = Section(text="A")
        s2 = Section(text="B")
        s1.emphases.append(EmphasisSpan(start=0, end=1, kind="b"))
        assert s2.emphases == []



# ── to_dict serialisation of emphases ─────────────────────────────────────────

class TestToDictWithEmphases:
    """Tests that Book.to_dict() serialises EmphasisSpan correctly."""

    def test_to_dict_serialises_section_emphases(self) -> None:
        """emphases list on Section appears in to_dict output."""
        span = EmphasisSpan(start=0, end=5, kind="em")
        section = Section(text="Hello world.", emphases=[span])
        chapter = Chapter(number=1, title="Chapter I", sections=[section])
        metadata = BookMetadata(
            title="T", author=None, releaseDate=None,
            language=None, originalPublication=None, credits=None,
        )
        book = Book(metadata=metadata, content=BookContent(chapters=[chapter]))

        result = book.to_dict()
        section_dict = result['content']['chapters'][0]['sections'][0]
        assert 'emphases' in section_dict
        assert len(section_dict['emphases']) == 1
        assert section_dict['emphases'][0]['start'] == 0
        assert section_dict['emphases'][0]['end'] == 5
        assert section_dict['emphases'][0]['kind'] == "em"

    def test_to_dict_serialises_empty_emphases_as_empty_list(self) -> None:
        """Section with no emphasis spans serialises as an empty list."""
        section = Section(text="Plain.")
        chapter = Chapter(number=1, title="Chapter I", sections=[section])
        metadata = BookMetadata(
            title="T", author=None, releaseDate=None,
            language=None, originalPublication=None, credits=None,
        )
        book = Book(metadata=metadata, content=BookContent(chapters=[chapter]))

        result = book.to_dict()
        section_dict = result['content']['chapters'][0]['sections'][0]
        assert section_dict['emphases'] == []


# ── Character ─────────────────────────────────────────────────────────────────

class TestCharacter:
    """Tests for the Character dataclass."""

    def test_create_character_with_required_fields(self) -> None:
        """Character stores character_id and name."""
        char = Character(character_id="harry", name="Harry Potter")
        assert char.character_id == "harry"
        assert char.name == "Harry Potter"

    def test_character_description_defaults_to_none(self) -> None:
        """Character description is optional and defaults to None."""
        char = Character(character_id="harry", name="Harry Potter")
        assert char.description is None

    def test_character_is_narrator_defaults_to_false(self) -> None:
        """Character is_narrator defaults to False."""
        char = Character(character_id="harry", name="Harry Potter")
        assert char.is_narrator is False

    def test_character_with_all_fields(self) -> None:
        """Character accepts all four fields."""
        char = Character(
            character_id="narrator",
            name="Narrator",
            description="A calm, authoritative voice",
            is_narrator=True
        )
        assert char.character_id == "narrator"
        assert char.name == "Narrator"
        assert char.description == "A calm, authoritative voice"
        assert char.is_narrator is True

    def test_narrator_character_id_is_reserved_string(self) -> None:
        """The narrator character uses the reserved id 'narrator'."""
        char = Character(character_id="narrator", name="Narrator", is_narrator=True)
        assert char.character_id == "narrator"

    def test_character_sex_defaults_to_none(self) -> None:
        """Character sex field defaults to None when not provided."""
        char = Character(character_id="harry", name="Harry Potter")
        assert char.sex is None

    def test_character_age_defaults_to_none(self) -> None:
        """Character age field defaults to None when not provided."""
        char = Character(character_id="harry", name="Harry Potter")
        assert char.age is None

    def test_character_accepts_sex_field(self) -> None:
        """Character accepts a sex value."""
        char = Character(character_id="harry", name="Harry Potter", sex="male")
        assert char.sex == "male"

    def test_character_accepts_age_field(self) -> None:
        """Character accepts an age value."""
        char = Character(character_id="harry", name="Harry Potter", age="young")
        assert char.age == "young"

    def test_character_with_all_six_fields(self) -> None:
        """Character can be constructed with all six fields."""
        char = Character(
            character_id="hermione",
            name="Hermione Granger",
            description="Brilliant witch",
            is_narrator=False,
            sex="female",
            age="young",
        )
        assert char.sex == "female"
        assert char.age == "young"
        assert char.description == "Brilliant witch"

    def test_existing_construction_still_works_after_new_fields(self) -> None:
        """Character(character_id=..., name=...) without sex/age still works."""
        char = Character(character_id="ron", name="Ron Weasley")
        assert char.character_id == "ron"
        assert char.name == "Ron Weasley"
        assert char.sex is None
        assert char.age is None


# ── Character.to_dict / from_dict ─────────────────────────────────────────────

class TestCharacterToDictFromDict:
    """Tests for Character.to_dict() and Character.from_dict()."""

    def test_to_dict_returns_dict_with_all_six_keys(self) -> None:
        """to_dict() includes character_id, name, description, is_narrator, sex, age."""
        char = Character(character_id="harry", name="Harry Potter", sex="male", age="young")
        result = char.to_dict()
        assert isinstance(result, dict)
        assert set(result.keys()) == {"character_id", "name", "description", "is_narrator", "sex", "age"}

    def test_to_dict_values_are_correct(self) -> None:
        """to_dict() returns correct values for all fields."""
        char = Character(
            character_id="harry",
            name="Harry Potter",
            description="The chosen one",
            is_narrator=False,
            sex="male",
            age="young",
        )
        result = char.to_dict()
        assert result["character_id"] == "harry"
        assert result["name"] == "Harry Potter"
        assert result["description"] == "The chosen one"
        assert result["is_narrator"] is False
        assert result["sex"] == "male"
        assert result["age"] == "young"

    def test_to_dict_none_fields_appear_as_none(self) -> None:
        """to_dict() preserves None for optional fields."""
        char = Character(character_id="narrator", name="Narrator", is_narrator=True)
        result = char.to_dict()
        assert result["description"] is None
        assert result["sex"] is None
        assert result["age"] is None

    def test_from_dict_constructs_character_with_all_fields(self) -> None:
        """from_dict() builds a Character from a complete dict."""
        d = {
            "character_id": "hermione",
            "name": "Hermione Granger",
            "description": "Brilliant witch",
            "is_narrator": False,
            "sex": "female",
            "age": "young",
        }
        char = Character.from_dict(d)
        assert char.character_id == "hermione"
        assert char.name == "Hermione Granger"
        assert char.description == "Brilliant witch"
        assert char.is_narrator is False
        assert char.sex == "female"
        assert char.age == "young"

    def test_from_dict_missing_sex_defaults_to_none(self) -> None:
        """from_dict() with no 'sex' key produces sex=None."""
        d = {"character_id": "ron", "name": "Ron Weasley"}
        char = Character.from_dict(d)
        assert char.sex is None

    def test_from_dict_missing_age_defaults_to_none(self) -> None:
        """from_dict() with no 'age' key produces age=None."""
        d = {"character_id": "ron", "name": "Ron Weasley"}
        char = Character.from_dict(d)
        assert char.age is None

    def test_from_dict_missing_description_defaults_to_none(self) -> None:
        """from_dict() with no 'description' key produces description=None."""
        d = {"character_id": "ron", "name": "Ron Weasley"}
        char = Character.from_dict(d)
        assert char.description is None

    def test_from_dict_missing_is_narrator_defaults_to_false(self) -> None:
        """from_dict() with no 'is_narrator' key produces is_narrator=False."""
        d = {"character_id": "ron", "name": "Ron Weasley"}
        char = Character.from_dict(d)
        assert char.is_narrator is False

    def test_round_trip_to_dict_from_dict(self) -> None:
        """to_dict() followed by from_dict() reconstructs the same Character."""
        original = Character(
            character_id="dumbledore",
            name="Albus Dumbledore",
            description="Headmaster",
            is_narrator=False,
            sex="male",
            age="elderly",
        )
        reconstructed = Character.from_dict(original.to_dict())
        assert reconstructed.character_id == original.character_id
        assert reconstructed.name == original.name
        assert reconstructed.description == original.description
        assert reconstructed.is_narrator == original.is_narrator
        assert reconstructed.sex == original.sex
        assert reconstructed.age == original.age

    def test_narrator_from_default_registry_has_sex_none(self) -> None:
        """Narrator built by with_default_narrator() has sex=None."""
        registry = CharacterRegistry.with_default_narrator()
        narrator = registry.get("narrator")
        assert narrator is not None
        assert narrator.sex is None

    def test_narrator_from_default_registry_has_age_none(self) -> None:
        """Narrator built by with_default_narrator() has age=None."""
        registry = CharacterRegistry.with_default_narrator()
        narrator = registry.get("narrator")
        assert narrator is not None
        assert narrator.age is None


# ── CharacterRegistry ─────────────────────────────────────────────────────────

class TestCharacterRegistry:
    """Tests for CharacterRegistry."""

    def test_with_default_narrator_returns_registry_with_narrator(self) -> None:
        """with_default_narrator() bootstraps a registry with the narrator entry."""
        registry = CharacterRegistry.with_default_narrator()
        assert len(registry.characters) == 1
        narrator = registry.characters[0]
        assert narrator.character_id == "narrator"
        assert narrator.is_narrator is True

    def test_with_default_narrator_narrator_name_is_set(self) -> None:
        """Narrator entry has a non-empty name."""
        registry = CharacterRegistry.with_default_narrator()
        assert registry.characters[0].name  # non-empty string

    def test_empty_registry_has_no_characters(self) -> None:
        """Default-constructed CharacterRegistry has an empty list."""
        registry = CharacterRegistry()
        assert registry.characters == []

    def test_get_returns_character_by_id(self) -> None:
        """get() finds a character by character_id."""
        char = Character(character_id="harry", name="Harry Potter")
        registry = CharacterRegistry(characters=[char])
        result = registry.get("harry")
        assert result is not None
        assert result.character_id == "harry"

    def test_get_returns_none_for_unknown_id(self) -> None:
        """get() returns None when character_id is not in registry."""
        registry = CharacterRegistry()
        assert registry.get("unknown") is None

    def test_add_inserts_character(self) -> None:
        """add() inserts a new character into the registry."""
        registry = CharacterRegistry()
        char = Character(character_id="hermione", name="Hermione Granger")
        registry.add(char)
        assert len(registry.characters) == 1
        assert registry.get("hermione") is not None

    def test_upsert_adds_new_character(self) -> None:
        """upsert() adds a character that does not yet exist."""
        registry = CharacterRegistry()
        char = Character(character_id="ron", name="Ron Weasley")
        registry.upsert(char)
        assert registry.get("ron") is not None

    def test_upsert_replaces_existing_character(self) -> None:
        """upsert() replaces an existing character with the same character_id."""
        registry = CharacterRegistry()
        original = Character(character_id="dumbledore", name="Old man")
        registry.add(original)
        updated = Character(
            character_id="dumbledore",
            name="Albus Dumbledore",
            description="Wise and old"
        )
        registry.upsert(updated)
        # Still one entry
        assert len(registry.characters) == 1
        found = registry.get("dumbledore")
        assert found is not None
        assert found.name == "Albus Dumbledore"
        assert found.description == "Wise and old"

    def test_upsert_does_not_duplicate(self) -> None:
        """Calling upsert twice for the same id results in exactly one entry."""
        registry = CharacterRegistry()
        registry.upsert(Character(character_id="snape", name="Professor Snape"))
        registry.upsert(Character(character_id="snape", name="Severus Snape"))
        assert len(registry.characters) == 1

    def test_get_narrator_from_default_registry(self) -> None:
        """get('narrator') works on a registry built with with_default_narrator()."""
        registry = CharacterRegistry.with_default_narrator()
        narrator = registry.get("narrator")
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

    def test_book_has_character_registry_field(self) -> None:
        """Book must have a character_registry attribute."""
        book = self._make_book()
        assert hasattr(book, "character_registry")

    def test_book_default_character_registry_is_character_registry_instance(self) -> None:
        """Default character_registry is a CharacterRegistry instance."""
        book = self._make_book()
        assert isinstance(book.character_registry, CharacterRegistry)

    def test_book_default_character_registry_has_narrator(self) -> None:
        """Default character_registry contains the narrator character."""
        book = self._make_book()
        assert book.character_registry.get("narrator") is not None

    def test_book_accepts_explicit_character_registry(self) -> None:
        """Book accepts an explicit CharacterRegistry at construction time."""
        registry = CharacterRegistry()
        char = Character(character_id="alice", name="Alice")
        registry.add(char)
        book = self._make_book(character_registry=registry)
        assert book.character_registry.get("alice") is not None

    def test_book_to_dict_does_not_include_character_registry(self) -> None:
        """to_dict() must NOT include a character_registry key."""
        book = self._make_book()
        result = book.to_dict()
        assert "character_registry" not in result

    def test_existing_book_construction_without_registry_still_works(self) -> None:
        """Book(metadata=..., content=...) with no registry kwarg must not raise."""
        section = Section(text="Once upon a time.")
        chapter = Chapter(number=1, title="Chapter I", sections=[section])
        metadata = BookMetadata(
            title="Test Book", author="Test Author", releaseDate=None,
            language=None, originalPublication=None, credits=None,
        )
        content = BookContent(chapters=[chapter])
        # Must not raise
        book = Book(metadata=metadata, content=content)
        assert book.metadata.title == "Test Book"
