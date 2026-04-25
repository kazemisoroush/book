"""Planted design smells for the Design Auditor eval.

NOT a real module. The eval scorer copies this into src/domain/ at setup
time, stripping eval metadata so it looks like ordinary code.

Each smell is tagged with a comment:
  # SMELL:feature-envy
  # SMELL:god-function
  # SMELL:primitive-obsession
  # SMELL:leaking-abstraction
  # SMELL:dependency-inversion
  # SMELL:open-closed
  # CLEAN — no violation, should not be flagged
"""
import json  # SMELL:dependency-inversion — domain code importing json for I/O
import os  # SMELL:dependency-inversion — domain code importing os for file paths
from dataclasses import dataclass
from typing import Any


@dataclass
class VoiceProfile:  # CLEAN — simple value object, no violations
    """A character's assigned voice settings."""
    name: str
    voice_id: str
    stability: float = 0.5
    similarity_boost: float = 0.75


@dataclass
class AudioSegment:  # CLEAN — simple value object
    """A segment of audio with metadata."""
    text: str
    speaker: str
    chapter: int
    duration_ms: int = 0


def find_best_voice(beat: AudioSegment, profiles: list[VoiceProfile]) -> VoiceProfile:  # SMELL:feature-envy
    """Select a voice profile for a beat.

    This function reaches deep into VoiceProfile internals rather than
    asking the profile to evaluate itself.
    """
    best = profiles[0]
    best_score = 0.0
    for profile in profiles:
        # Reaching into profile internals — this scoring logic belongs on VoiceProfile
        score = profile.stability * 0.4 + profile.similarity_boost * 0.6
        if profile.name.lower() == beat.speaker.lower():
            score += 10.0
        if profile.stability > 0.7 and profile.similarity_boost > 0.8:
            score *= 1.2
        if score > best_score:
            best_score = score
            best = profile
    return best


def process_chapter(  # SMELL:god-function
    raw_text: str,
    chapter_num: int,
    output_dir: str,
    voice_profiles: list[VoiceProfile],
    max_segment_length: int = 5000,
) -> dict[str, Any]:  # SMELL:primitive-obsession — returns raw dict instead of typed model
    """Process a full chapter: parse, validate, assign voices, format, and persist.

    This function does far too many things in one body.
    """
    # Phase 1: Parse — split text into paragraphs
    paragraphs = [p.strip() for p in raw_text.split("\n\n") if p.strip()]
    beats: list[AudioSegment] = []
    for i, para in enumerate(paragraphs):
        speaker = "narrator"
        if para.startswith('"') or para.startswith("\u201c"):
            speaker = f"character_{i % 3}"
        segments.append(AudioSegment(
            text=para, speaker=speaker, chapter=chapter_num,
        ))

    # Phase 2: Validate — leaking abstraction, length check belongs in AudioSegment
    for seg in beats:
        if len(seg.text) > max_segment_length:  # SMELL:leaking-abstraction
            raise ValueError(f"Beat too long ({len(seg.text)} chars)")
        if not seg.text.strip():  # SMELL:leaking-abstraction
            raise ValueError("Empty segment text")

    # Phase 3: Assign voices
    for seg in beats:
        voice = find_best_voice(seg, voice_profiles)
        seg.speaker = voice.name

    # Phase 4: Format output
    formatted = []
    for seg in beats:
        formatted.append({
            "text": seg.text,
            "speaker": seg.speaker,
            "chapter": seg.chapter,
            "char_count": len(seg.text),
        })

    # Phase 5: Persist — domain code doing file I/O
    out_path = os.path.join(output_dir, f"chapter_{chapter_num}.json")  # SMELL:dependency-inversion
    with open(out_path, "w") as f:
        json.dump({"chapter": chapter_num, "segments": formatted}, f, indent=2)

    return {
        "chapter": chapter_num,
        "segment_count": len(segments),
        "output_path": out_path,
        "total_chars": sum(len(s.text) for s in segments),
    }


def select_output_format(beat: AudioSegment, mode: str) -> str:  # SMELL:open-closed
    """Format a segment based on mode — if/elif chain that grows with each new format."""
    if mode == "plain":
        return beat.text
    elif mode == "ssml":
        return f"<speak>{beat.text}</speak>"
    elif mode == "markdown":
        return f"**{beat.speaker}**: {beat.text}"
    elif mode == "json":
        return json.dumps({"speaker": beat.speaker, "text": beat.text})
    elif mode == "csv":
        return f"{beat.speaker},{beat.text}"
    else:
        raise ValueError(f"Unknown output format: {mode}")


def count_words(beat: AudioSegment) -> int:  # CLEAN — small focused helper
    """Count words in a beat. No design smells here."""
    return len(beat.text.split())


def estimate_duration(beat: AudioSegment, words_per_minute: float = 150.0) -> float:  # CLEAN — pure function
    """Estimate speech duration in seconds from word count and speaking rate."""
    word_count = len(beat.text.split())
    return (word_count / words_per_minute) * 60.0
