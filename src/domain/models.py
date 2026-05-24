"""Core domain models for the audiobook pipeline."""
from dataclasses import asdict, dataclass, field
from typing import Optional

from src.domain.beat import Beat, BeatType


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

    @property
    def voice_design_prompt(self) -> Optional[str]:
        """Derive the ElevenLabs voice-design prompt from stored fields.

        Returns ``None`` for narrators or characters without a description.
        """
        if self.is_narrator or not self.description:
            return None
        desc = self.description.rstrip(".")
        return f"{self.age} {self.sex}, {desc}."

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


@dataclass(frozen=True)
class Scene:
    """Acoustic environment of a stretch of narrative (value object).

    Describes *where* the action takes place so that TTS voice settings
    can be adjusted to match the setting (e.g. slower pacing in a cave,
    more projection on a battlefield).

    Two chapters in the same cave share equivalent ``Scene`` instances
    but are not the "same" scene -- this is a value object, not an entity.
    """

    scene_id: str
    environment: str
    acoustic_hints: list[str] = field(default_factory=list)
    voice_modifiers: dict[str, float] = field(default_factory=dict)
    ambient_prompt: Optional[str] = None
    ambient_volume: Optional[float] = None


@dataclass
class SceneRegistry:
    """Registry of all scenes discovered while processing a book.

    Holds a dict of ``scene_id -> Scene``.  Scenes are upserted by the AI
    section parser as it detects environment changes.  The registry is
    threaded through parsing just like :class:`CharacterRegistry`.
    """

    _scenes: dict[str, Scene] = field(default_factory=dict)

    def upsert(self, scene: Scene) -> None:
        """Add *scene* if absent, or replace the existing entry if present."""
        self._scenes[scene.scene_id] = scene

    def get(self, scene_id: str) -> Optional[Scene]:
        """Return the scene with *scene_id*, or ``None`` if absent."""
        return self._scenes.get(scene_id)

    def all(self) -> list[Scene]:
        """Return all registered scenes."""
        return list(self._scenes.values())

    def to_dict(self) -> list[dict[str, object]]:
        """Return a JSON-serialisable list of scene dictionaries."""
        result: list[dict[str, object]] = []
        for scene in self._scenes.values():
            result.append({
                "scene_id": scene.scene_id,
                "environment": scene.environment,
                "acoustic_hints": list(scene.acoustic_hints),
                "voice_modifiers": dict(scene.voice_modifiers),
                "ambient_prompt": scene.ambient_prompt,
                "ambient_volume": scene.ambient_volume,
            })
        return result

    @classmethod
    def from_dict(cls, data: list[dict[str, object]]) -> "SceneRegistry":
        """Construct a SceneRegistry from a list of scene dicts."""
        registry = cls()
        for item in data:
            raw_hints = item.get("acoustic_hints", [])
            raw_mods = item.get("voice_modifiers", {})
            raw_prompt = item.get("ambient_prompt")
            raw_vol = item.get("ambient_volume")
            scene = Scene(
                scene_id=str(item["scene_id"]),
                environment=str(item["environment"]),
                acoustic_hints=[str(h) for h in raw_hints],  # type: ignore[attr-defined]
                voice_modifiers={
                    str(k): float(v)  # type: ignore[arg-type]
                    for k, v in raw_mods.items()  # type: ignore[attr-defined]
                },
                ambient_prompt=str(raw_prompt) if raw_prompt is not None else None,
                ambient_volume=float(raw_vol) if raw_vol is not None else None,  # type: ignore[arg-type]
            )
            registry.upsert(scene)
        return registry


@dataclass
class Chapter:
    """A chapter containing multiple sections (paragraphs)."""
    number: int
    title: str
    sections: list[Section]
    ambient_audio_paths: list[str] = field(default_factory=list)
    sfx_audio_paths: list[str] = field(default_factory=list)
    music_audio_paths: list[str] = field(default_factory=list)


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
        default_factory=CharacterRegistry.with_default_narrator
    )
    scene_registry: "SceneRegistry" = field(
        default_factory=SceneRegistry
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
            "scene_registry": self.scene_registry.to_dict(),
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
                            scene_id=s.get("scene_id"),
                            emotion=s.get("emotion"),
                            voice_stability=s.get("voice_stability"),
                            voice_style=s.get("voice_style"),
                            voice_speed=s.get("voice_speed"),
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
                ambient_audio_paths=ch.get("ambient_audio_paths", []),
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

        scene_reg = SceneRegistry.from_dict(data["scene_registry"])

        return cls(
            metadata=metadata,
            content=content,
            character_registry=registry,
            scene_registry=scene_reg,
        )
