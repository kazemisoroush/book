"""Core domain models for the audiobook pipeline."""
import re
from dataclasses import asdict, dataclass, field
from typing import Optional

from src.domain.beat import Beat, BeatType
from src.domain.character import Character
from src.domain.character_id import slugify_name
from src.domain.character_registry import CharacterRegistry

_AUTHOR_DATE_RANGE = re.compile(r",\s*\d{4}\s*-\s*\d{4}\s*$")


def _normalize_author(raw: str) -> str:
    """Strip the trailing date range and flip 'Last, First' to 'First Last'."""
    without_dates = _AUTHOR_DATE_RANGE.sub("", raw).strip()
    if "," in without_dates:
        last, first = without_dates.split(",", 1)
        return f"{first.strip()} {last.strip()}"
    return without_dates


@dataclass
class Section:
    """A section (paragraph) of text, optionally broken into beats.

    A section represents a paragraph. Simple narration paragraphs
    have just text. Paragraphs with dialogue are broken down into
    beats (dialogue/narration).

    ``section_type`` is an optional classifier set by the static content
    parser (e.g. ``"illustration"``).  When set, the AI section parser
    skips the LLM call and passes the section through unchanged.
    """
    text: str
    beats: Optional[list[Beat]] = None
    section_type: Optional[str] = None


@dataclass
class Chapter:
    """A chapter containing multiple sections (paragraphs)."""
    number: int
    title: str
    sections: list[Section]
    sfx_audio_paths: list[str] = field(default_factory=list)
    music_audio_paths: list[str] = field(default_factory=list)

    @property
    def is_first(self) -> bool:
        """True when this is the first chapter of the book."""
        return self.number == 1


@dataclass
class BookMetadata:
    """Book metadata containing bibliographic information."""
    title: str
    author: Optional[str]
    releaseDate: Optional[str]
    language: Optional[str]
    originalPublication: Optional[str]
    credits: Optional[str]

    @property
    def book_id(self) -> str:
        """Stable, filesystem-safe identifier derived from the metadata.

        Format: ``{title_slug}:{author_slug}`` with author normalized to
        ``First Last`` and trailing date ranges stripped. Falls back to
        ``"untitled"`` / ``"unknown"`` when the corresponding field is missing.
        """
        title_slug = slugify_name(self.title) if self.title else "untitled"
        author_slug = (
            slugify_name(_normalize_author(self.author)) if self.author else "unknown"
        )
        return f"{title_slug}:{author_slug}"


@dataclass
class BookContent:
    """Book content containing chapters and sections."""
    chapters: list[Chapter]


@dataclass
class BookParseContext:
    """Context for AI beatation: the book, chapters to parse, and full content.

    Produced by :class:`BookSource.get_book` to give the
    workflow everything it needs without touching download/cache internals.

    ``book`` may already contain cached chapters and registries.
    ``chapters_to_parse`` lists only chapters that still need AI beatation.
    ``content`` is the full parsed content (all chapters) for reference.
    """

    book: "Book"
    chapters_to_parse: list[Chapter]
    content: BookContent


@dataclass
class Book:
    """Complete book with metadata and content."""
    metadata: BookMetadata
    content: BookContent
    character_registry: "CharacterRegistry" = field(
        default_factory=CharacterRegistry,
    )

    @property
    def book_id(self) -> str:
        """Stable, filesystem-safe identifier; delegates to :attr:`metadata`."""
        return self.metadata.book_id

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
            if isinstance(obj, BeatType):
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

        Restores ``metadata``, ``content`` (chapters / sections / beats),
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

        # Reconstruct content (chapters → sections → beats)
        chapters: list[Chapter] = []
        for ch in data["content"]["chapters"]:
            sections: list[Section] = []
            for sec in ch["sections"]:
                beats: Optional[list[Beat]] = None
                raw_beats = sec.get("beats")
                if raw_beats is not None:
                    beats = [
                        Beat(
                            text=s["text"],
                            beat_type=BeatType(s["beat_type"]),
                            character_id=s.get("character_id"),
                            emotion=s.get("emotion"),
                        )
                        for s in raw_beats
                    ]
                sections.append(Section(
                    text=sec["text"],
                    beats=beats,
                    section_type=sec.get("section_type"),
                ))
            chapters.append(Chapter(
                number=ch["number"],
                title=ch["title"],
                sections=sections,
                sfx_audio_paths=ch.get("sfx_audio_paths", []),
                music_audio_paths=ch.get("music_audio_paths", []),
            ))
        content = BookContent(chapters=chapters)

        # Reconstruct character registry
        registry = CharacterRegistry(
            characters=[
                Character.from_dict(c) for c in data.get("character_registry", [])
            ]
        )

        return cls(
            metadata=metadata,
            content=content,
            character_registry=registry,
        )
