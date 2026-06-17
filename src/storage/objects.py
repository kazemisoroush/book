"""Value objects passed to and from AudioStore so callers never handle storage keys."""
from dataclasses import dataclass
from typing import Any, Literal, Mapping

TrimStep = int | Literal["final"]


@dataclass(frozen=True)
class TTSBeatRef:
    """Identity of one per-beat TTS audio artifact."""

    book_id: str
    provider: str
    index: int


@dataclass(frozen=True)
class TTSBeat:
    """A per-beat TTS audio artifact with its bytes."""

    book_id: str
    provider: str
    index: int
    audio: bytes

    @property
    def ref(self) -> TTSBeatRef:
        return TTSBeatRef(self.book_id, self.provider, self.index)


@dataclass(frozen=True)
class TTSChunkRef:
    """Identity of one dialogue-API chunk artifact."""

    book_id: str
    provider: str
    chapter_slug: str
    index: int


@dataclass(frozen=True)
class TTSChunk:
    """A dialogue-API chunk artifact with its bytes."""

    book_id: str
    provider: str
    chapter_slug: str
    index: int
    audio: bytes

    @property
    def ref(self) -> TTSChunkRef:
        return TTSChunkRef(self.book_id, self.provider, self.chapter_slug, self.index)


@dataclass(frozen=True)
class SFXBeatRef:
    """Identity of one per-beat SFX clip."""

    book_id: str
    provider: str
    index: int
    extension: str = "mp3"


@dataclass(frozen=True)
class SFXBeat:
    """A per-beat SFX clip with its bytes."""

    book_id: str
    provider: str
    index: int
    audio: bytes
    extension: str = "mp3"

    @property
    def ref(self) -> SFXBeatRef:
        return SFXBeatRef(self.book_id, self.provider, self.index, self.extension)


@dataclass(frozen=True)
class SilenceClipRef:
    """Identity of a cached silence clip used between beats in the mix."""

    book_id: str
    provider: str
    duration_ms: int


@dataclass(frozen=True)
class MixOutputRef:
    """Identity of one final per-chapter mix output."""

    book_id: str
    provider: str
    chapter_slug: str


@dataclass(frozen=True)
class TrimStepRef:
    """Identity of one chained trimmer intermediate (or the final trimmed sibling)."""

    beat: TTSBeatRef
    step: TrimStep


@dataclass(frozen=True)
class VoiceRequestRef:
    """Identity of one per-character voice API request artifact."""

    book_id: str
    character_slug: str
    name: str


@dataclass(frozen=True)
class APIRequest:
    """One outbound API call captured as a sidecar artifact."""

    method: str
    url: str
    headers: Mapping[str, str]
    body: Any
