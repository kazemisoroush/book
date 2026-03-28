"""Core domain models for the audiobook pipeline."""
from dataclasses import dataclass, asdict, field
from enum import Enum
from typing import Optional


@dataclass
class Character:
    """A voice character in the audiobook.

    A character maps 1-to-1 with a TTS voice slot.  The narrator is
    a character too — its ``character_id`` is the reserved string
    ``"narrator"``.

    ``character_id`` is a stable slug (e.g. ``"harry_potter"`` or a UUID).
    ``name`` is the human-readable display name used in prompts and logs.
    ``description`` is an optional voice description for TTS assignment.
    ``is_narrator`` marks the default narration voice.
    """

    character_id: str
    name: str
    description: Optional[str] = None
    is_narrator: bool = False
    sex: Optional[str] = None
    age: Optional[str] = None

    def to_dict(self) -> dict:  # type: ignore[type-arg]
        """Return a JSON-serialisable dictionary of all fields."""
        return {
            "character_id": self.character_id,
            "name": self.name,
            "description": self.description,
            "is_narrator": self.is_narrator,
            "sex": self.sex,
            "age": self.age,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Character":  # type: ignore[type-arg]
        """Construct a Character from a dictionary.

        Missing optional keys default to ``None`` (for ``description``,
        ``sex``, ``age``) or ``False`` (for ``is_narrator``).
        """
        return cls(
            character_id=data["character_id"],
            name=data["name"],
            description=data.get("description"),
            is_narrator=data.get("is_narrator", False),
            sex=data.get("sex"),
            age=data.get("age"),
        )


@dataclass
class CharacterRegistry:
    """Registry of all voice characters discovered while processing a book.

    Always bootstrapped with at least the default narrator entry via
    :meth:`with_default_narrator`.  Characters are eventually-consistent:
    a character may exist with no voice assigned yet.

    The registry is threaded through the AI section parser pipeline so
    that character IDs remain consistent across the entire book.
    """

    characters: list[Character] = field(default_factory=list)

    @classmethod
    def with_default_narrator(cls) -> "CharacterRegistry":
        """Return a registry pre-populated with the default narrator entry."""
        narrator = Character(
            character_id="narrator",
            name="Narrator",
            description=None,
            is_narrator=True,
        )
        return cls(characters=[narrator])

    def get(self, character_id: str) -> Optional[Character]:
        """Return the character with ``character_id``, or None if absent."""
        for char in self.characters:
            if char.character_id == character_id:
                return char
        return None

    def add(self, character: Character) -> None:
        """Append a new character.  Does not check for duplicates."""
        self.characters.append(character)

    def upsert(self, character: Character) -> None:
        """Add *character* if absent, or replace the existing entry if present."""
        for i, char in enumerate(self.characters):
            if char.character_id == character.character_id:
                self.characters[i] = character
                return
        self.characters.append(character)


class SegmentType(Enum):
    """Type of text segment."""
    NARRATION = "narration"
    DIALOGUE = "dialogue"
    ILLUSTRATION = "illustration"
    COPYRIGHT = "copyright"
    OTHER = "other"  # Non-narratable content (page numbers, metadata markers, etc.)


@dataclass
class EmphasisSpan:
    """A span of emphasised text within a Section.

    Character offsets refer to the plain-text ``text`` field of the
    containing Section.  ``start`` is inclusive, ``end`` is exclusive
    — matching Python slice semantics.

    ``kind`` records which HTML inline element (or equivalent markup)
    produced the emphasis: one of ``"em"``, ``"b"``, ``"strong"``,
    ``"i"``.  This is a universal abstraction — the HTML adapter is
    merely one producer; future EPUB or plain-text producers may
    populate the same field.
    """
    start: int
    end: int
    kind: str


@dataclass
class Segment:
    """A single piece of text (narration or dialogue).

    ``character_id`` is a stable reference into ``CharacterRegistry``.
    Narration segments use the reserved id ``"narrator"``.
    Dialogue segments use the speaker's registry id.
    """

    text: str
    segment_type: SegmentType
    character_id: Optional[str] = None  # Foreign key into CharacterRegistry

    def is_dialogue(self) -> bool:
        return self.segment_type == SegmentType.DIALOGUE

    def is_narration(self) -> bool:
        return self.segment_type == SegmentType.NARRATION

    def is_illustration(self) -> bool:
        return self.segment_type == SegmentType.ILLUSTRATION

    def is_copyright(self) -> bool:
        return self.segment_type == SegmentType.COPYRIGHT

    def is_other(self) -> bool:
        return self.segment_type == SegmentType.OTHER


@dataclass
class Section:
    """A section (paragraph) of text, optionally segmented.

    A section represents a paragraph. Simple narration paragraphs
    have just text. Paragraphs with dialogue are broken down into
    segments (dialogue/narration).

    ``emphases`` records inline emphasis spans (from ``<em>``, ``<b>``,
    ``<strong>``, ``<i>`` in HTML sources, or equivalent in other
    formats).  Character offsets are relative to ``text``.
    """
    text: str
    segments: Optional[list[Segment]] = None
    emphases: list[EmphasisSpan] = field(default_factory=list)


@dataclass
class Chapter:
    """A chapter containing multiple sections (paragraphs)."""
    number: int
    title: str
    sections: list[Section]


@dataclass
class BookMetadata:
    """Book metadata containing bibliographic information."""
    title: str
    author: Optional[str]
    releaseDate: Optional[str]
    language: Optional[str]
    originalPublication: Optional[str]
    credits: Optional[str]


@dataclass
class BookContent:
    """Book content containing chapters and sections."""
    chapters: list[Chapter]


@dataclass
class Book:
    """Complete book with metadata and content."""
    metadata: BookMetadata
    content: BookContent
    character_registry: "CharacterRegistry" = field(
        default_factory=CharacterRegistry.with_default_narrator
    )

    def to_dict(self) -> dict:  # type: ignore[type-arg]
        """Convert Book to JSON-serializable dictionary.

        Recursively converts all dataclasses and enums to dictionaries
        and strings respectively.  The ``character_registry`` is serialised
        as a list of ``Character.to_dict()`` entries under the
        ``"character_registry"`` key.

        Returns:
            Dictionary representation suitable for JSON serialization
        """
        def convert_value(obj):  # type: ignore[no-untyped-def]
            """Recursively convert objects to JSON-serializable types."""
            if isinstance(obj, SegmentType):
                return obj.value
            elif hasattr(obj, '__dataclass_fields__'):
                return {
                    k: convert_value(v)
                    for k, v in asdict(obj).items()
                }
            elif isinstance(obj, list):
                return [convert_value(item) for item in obj]
            elif isinstance(obj, dict):
                return {key: convert_value(val) for key, val in obj.items()}
            else:
                return obj

        return {
            "metadata": convert_value(asdict(self.metadata)),
            "content": convert_value(asdict(self.content)),
            "character_registry": [
                char.to_dict() for char in self.character_registry.characters
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Book":  # type: ignore[type-arg]
        """Construct a Book from a dictionary produced by :meth:`to_dict`.

        Restores ``metadata``, ``content`` (chapters / sections / segments),
        and ``character_registry`` (list of :class:`Character` entries).

        Args:
            data: Dictionary as returned by ``Book.to_dict()``.

        Returns:
            A fully reconstructed :class:`Book` instance.
        """
        # Reconstruct metadata
        m = data["metadata"]
        metadata = BookMetadata(
            title=m["title"],
            author=m.get("author"),
            releaseDate=m.get("releaseDate"),
            language=m.get("language"),
            originalPublication=m.get("originalPublication"),
            credits=m.get("credits"),
        )

        # Reconstruct content (chapters → sections → segments)
        chapters: list[Chapter] = []
        for ch in data["content"]["chapters"]:
            sections: list[Section] = []
            for sec in ch["sections"]:
                segments: Optional[list[Segment]] = None
                if sec.get("segments") is not None:
                    segments = [
                        Segment(
                            text=s["text"],
                            segment_type=SegmentType(s["segment_type"]),
                            character_id=s.get("character_id"),
                        )
                        for s in sec["segments"]
                    ]
                emphases: list[EmphasisSpan] = [
                    EmphasisSpan(start=e["start"], end=e["end"], kind=e["kind"])
                    for e in sec.get("emphases", [])
                ]
                sections.append(Section(
                    text=sec["text"],
                    segments=segments,
                    emphases=emphases,
                ))
            chapters.append(Chapter(
                number=ch["number"],
                title=ch["title"],
                sections=sections,
            ))
        content = BookContent(chapters=chapters)

        # Reconstruct character registry
        registry = CharacterRegistry(
            characters=[
                Character.from_dict(c) for c in data.get("character_registry", [])
            ]
        )

        return cls(metadata=metadata, content=content, character_registry=registry)
