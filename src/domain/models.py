"""Core domain models for the audiobook pipeline."""
from dataclasses import dataclass, asdict, field
from enum import Enum
from typing import Optional


@dataclass(frozen=True)
class AIPrompt:
    """Structured prompt for LLM calls with cache-friendly builder methods.

    This is a frozen value object representing a segmented prompt suitable for
    caching. The prompt is composed of 6 logical parts:

    - **static_instructions**: Immutable rules and format instructions
    - **book_context**: Book title and author (varies per book, static for a book)
    - **character_registry**: Current character list (varies per section, part of cache key)
    - **surrounding_context**: Preceding sections for speaker inference (dynamic per section)
    - **scene_registry**: Known scenes for reuse (dynamic per section)
    - **text_to_segment**: The section text to parse (dynamic per section)

    The builder methods expose the cacheable vs. dynamic split for LLM providers
    (e.g., AWS Bedrock prompt caching).
    """

    static_instructions: str
    book_context: str
    character_registry: str
    surrounding_context: str
    scene_registry: str
    text_to_segment: str

    def build_static_portion(self) -> str:
        """Return the cacheable portion of the prompt.

        This includes static_instructions and book_context — the parts that
        don't change across multiple API calls for the same book.

        Returns:
            Concatenated static_instructions + book_context
        """
        return self.static_instructions + self.book_context

    def build_dynamic_portion(self) -> str:
        """Return the dynamic (non-cacheable) portion of the prompt.

        This includes the character registry, surrounding context, scene registry,
        and the text to segment — parts that change with every section.

        Returns:
            Concatenated character_registry + surrounding_context + scene_registry + text_to_segment
        """
        return self.character_registry + self.surrounding_context + self.scene_registry + self.text_to_segment

    def build_full_prompt(self) -> str:
        """Return the complete prompt as a single string.

        Concatenates all 6 fields in order: static first, then dynamic.
        Useful for backward compatibility or debugging.

        Returns:
            Concatenated static_portion + dynamic_portion
        """
        return self.build_static_portion() + self.build_dynamic_portion()


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
    voice_design_prompt: Optional[str] = None

    def to_dict(self) -> dict:  # type: ignore[type-arg]
        """Return a JSON-serialisable dictionary of all fields."""
        return {
            "character_id": self.character_id,
            "name": self.name,
            "description": self.description,
            "is_narrator": self.is_narrator,
            "sex": self.sex,
            "age": self.age,
            "voice_design_prompt": self.voice_design_prompt,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Character":  # type: ignore[type-arg]
        """Construct a Character from a dictionary.

        Missing optional keys default to ``None`` (for ``description``,
        ``sex``, ``age``, ``voice_design_prompt``) or ``False`` (for
        ``is_narrator``).
        """
        return cls(
            character_id=data["character_id"],
            name=data["name"],
            description=data.get("description"),
            is_narrator=data.get("is_narrator", False),
            sex=data.get("sex"),
            age=data.get("age"),
            voice_design_prompt=data.get("voice_design_prompt"),
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
class Segment:
    """A single piece of text (narration or dialogue).

    ``character_id`` is a stable reference into ``CharacterRegistry``.
    Narration segments use the reserved id ``"narrator"``.
    Dialogue segments use the speaker's registry id.

    ``scene_id`` is an optional reference into ``SceneRegistry``.  When set,
    it indicates the acoustic environment for this segment.  ``None`` means
    no scene was detected (no scene modifiers are applied).

    ``emotion`` records the character's inner state at the time of speaking,
    assigned by the AI during segmentation.  ``None`` or ``"neutral"`` means
    no emotional colouring — these segments use the neutral voice-settings
    preset.  Narration segments always use ``None``.

    The value is a free-form lowercase auditory tag (e.g. ``"whispers"``,
    ``"laughs harder"``, ``"sarcastic"``).  Any auditory string is forwarded
    to the TTS API as-is.

    ``sound_effect_description`` is an optional natural-language description of
    a diegetic sound effect to be inserted at this segment (e.g., "dry cough",
    "firm knock on wooden door"). Only set when the narrative explicitly
    describes a sound-worthy action (US-023).
    """

    text: str
    segment_type: SegmentType
    character_id: Optional[str] = None  # Foreign key into CharacterRegistry
    scene_id: Optional[str] = None  # Foreign key into SceneRegistry
    emotion: Optional[str] = None
    voice_stability: Optional[float] = None
    voice_style: Optional[float] = None
    voice_speed: Optional[float] = None
    sound_effect_description: Optional[str] = None

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

    @property
    def is_narratable(self) -> bool:
        """True when the segment should be read aloud (dialogue or narration)."""
        return self.segment_type in {SegmentType.DIALOGUE, SegmentType.NARRATION}


@dataclass
class Section:
    """A section (paragraph) of text, optionally segmented.

    A section represents a paragraph. Simple narration paragraphs
    have just text. Paragraphs with dialogue are broken down into
    segments (dialogue/narration).

    ``section_type`` is an optional classifier set by the static content
    parser (e.g. ``"illustration"``).  When set, the AI section parser
    skips the LLM call and passes the section through unchanged.
    """
    text: str
    segments: Optional[list[Segment]] = None
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
            "scene_registry": self.scene_registry.to_dict(),
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
                            scene_id=s.get("scene_id"),
                            emotion=s.get("emotion"),
                            voice_stability=s.get("voice_stability"),
                            voice_style=s.get("voice_style"),
                            voice_speed=s.get("voice_speed"),
                            sound_effect_description=s.get("sound_effect_description"),
                        )
                        for s in sec["segments"]
                    ]
                sections.append(Section(
                    text=sec["text"],
                    segments=segments,
                    section_type=sec.get("section_type"),
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

        # Reconstruct scene registry (absent in legacy data)
        scene_reg = SceneRegistry.from_dict(data.get("scene_registry", []))  # type: ignore[arg-type]

        return cls(
            metadata=metadata,
            content=content,
            character_registry=registry,
            scene_registry=scene_reg,
        )
