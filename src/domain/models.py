"""Core domain models for the audiobook pipeline."""
import re
from dataclasses import asdict, dataclass, field
from typing import Optional

from src.domain.beat import Beat, BeatType
from src.domain.character import Character
from src.domain.character_id import slugify_name
from src.domain.character_registry import CharacterRegistry
from src.domain.voice_settings import VoiceSettings

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
    """A pre-AI input paragraph: raw text with an optional section_type classifier."""
    text: str
    section_type: Optional[str] = None


@dataclass
class Chapter:
    """A chapter with input sections (pre-AI) and beats (post-AI)."""
    number: int
    title: str
    label: Optional[str] = None
    sections: list[Section] = field(default_factory=list)
    beats: list[Beat] = field(default_factory=list)
    sfx_audio_paths: list[str] = field(default_factory=list)
    music_audio_paths: list[str] = field(default_factory=list)

    @property
    def is_first(self) -> bool:
        """True when this is the first chapter of the book."""
        return self.number == 1

    @property
    def display_name(self) -> str:
        """Human-readable label like ``"Chapter 3"`` or ``"Letter 1"``."""
        return self.label if self.label else f"Chapter {self.number}"

    @property
    def dir_slug(self) -> str:
        """File-system slug like ``"chapter_007"``."""
        return f"chapter_{self.number:03d}"


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

    @property
    def display_author(self) -> Optional[str]:
        """The author for display: ``First Last`` with trailing date ranges stripped."""
        return _normalize_author(self.author) if self.author else None


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
    voice_assignments: dict[int, str] = field(default_factory=dict)
    source_url: Optional[str] = None

    @property
    def book_id(self) -> str:
        """Stable, filesystem-safe identifier; delegates to :attr:`metadata`."""
        return self.metadata.book_id

    def to_dict(self) -> dict:  # type: ignore[type-arg]
        """Convert Book to a JSON-serializable dictionary."""
        def convert_value(obj):  # type: ignore[no-untyped-def]
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

        content_dict = convert_value(asdict(self.content))
        for chapter in content_dict["chapters"]:
            for key in ("sections", "beats", "sfx_audio_paths", "music_audio_paths"):
                if not chapter.get(key):
                    chapter.pop(key, None)
            if not chapter.get("title"):
                chapter.pop("title", None)
            if chapter.get("label") is None:
                chapter.pop("label", None)
            for beat in chapter.get("beats", []):
                for key in [k for k, v in beat.items() if v is None]:
                    del beat[key]

        result: dict = {  # type: ignore[type-arg]
            "metadata": convert_value(asdict(self.metadata)),
            "content": content_dict,
        }
        if self.character_registry.characters:
            result["character_registry"] = [
                char.to_dict() for char in self.character_registry.characters
            ]
        if self.voice_assignments:
            result["voice_assignments"] = {
                str(k): v for k, v in self.voice_assignments.items()
            }
        if self.source_url:
            result["source_url"] = self.source_url
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "Book":  # type: ignore[type-arg]
        """Construct a Book from a dictionary produced by :meth:`to_dict`."""
        m = data["metadata"]
        metadata = BookMetadata(
            title=m["title"],
            author=m.get("author"),
            releaseDate=m.get("releaseDate"),
            language=m.get("language"),
            originalPublication=m.get("originalPublication"),
            credits=m.get("credits"),
        )

        chapters: list[Chapter] = []
        for ch in data["content"]["chapters"]:
            sections: list[Section] = []
            for sec in ch.get("sections", []):
                sections.append(Section(
                    text=sec["text"],
                    section_type=sec.get("section_type"),
                ))
            beats: list[Beat] = [
                Beat(
                    text=b["text"],
                    beat_type=BeatType(b["beat_type"]),
                    character_id=b.get("character_id"),
                    emotion=b.get("emotion"),
                    voice_settings=(
                        VoiceSettings(**b["voice_settings"])
                        if b.get("voice_settings") is not None
                        else None
                    ),
                    voice_id=b.get("voice_id"),
                )
                for b in ch.get("beats", [])
            ]
            chapters.append(Chapter(
                number=ch["number"],
                title=ch.get("title", ""),
                label=ch.get("label"),
                sections=sections,
                beats=beats,
                sfx_audio_paths=ch.get("sfx_audio_paths", []),
                music_audio_paths=ch.get("music_audio_paths", []),
            ))
        content = BookContent(chapters=chapters)

        registry = CharacterRegistry(
            characters=[
                Character.from_dict(c) for c in data.get("character_registry", [])
            ]
        )

        voice_assignments: dict[int, str] = {
            int(k): v for k, v in data.get("voice_assignments", {}).items()
        }

        return cls(
            metadata=metadata,
            content=content,
            character_registry=registry,
            voice_assignments=voice_assignments,
            source_url=data.get("source_url"),
        )
