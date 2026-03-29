# US-009 — Emotion-Aware TTS

## Goal

Make characters sound the way they feel. The AI parser detects the
emotional tone of each spoken segment and encodes it as a structured
tag. The TTS layer reads that tag and uses ElevenLabs' eleven_v3 inline
audio-tag syntax to deliver the line with the matching emotional
performance.

---

## Background / motivation

Today every segment is synthesised with flat voice settings regardless
of whether a character is whispering a secret, crying a farewell, or
shouting in rage. The pipeline already knows _who_ speaks each line;
this spec adds _how_ they feel when they speak it.

The key insight is that Sonnet 4.6 and ElevenLabs eleven_v3 share a
common vocabulary. ElevenLabs eleven_v3 accepts inline audio tags
(`[angry]`, `[whispering]`, etc.) embedded directly in the text string.
Sonnet can read narrative context and literary cues to pick the right
tag from a fixed vocabulary. Constraining both ends to the same enum
makes the handshake reliable and testable.

---

## Acceptance criteria

1. A new `EmotionTag` string enum exists in `src/domain/models.py` with
   exactly these values:

   ```
   NEUTRAL    EXCITED    ANGRY      SAD        FEARFUL
   WHISPERING CRYING     LAUGHING   STERN      GENTLE
   ```

   These 10 labels were chosen because: (a) ElevenLabs eleven_v3
   responds reliably to them, (b) they cover the full dramatic range of
   classic fiction, (c) Sonnet can infer them from textual cues without
   hallucination risk.

2. `Segment` gains one new optional field: `emotion: Optional[EmotionTag] = None`.
   `Segment.to_dict()` / `from_dict()` serialise it as a nullable string.
   Default is `None` (treated as `NEUTRAL` at synthesis time).

3. The AI segmentation prompt (`AISectionParser`) is updated to output
   an `emotion` field per segment alongside the existing `speaker_id`
   and `type` fields. The prompt instructs the model to:
   - Pick the emotion that best fits the character's _inner state_ at
     the time of speaking, not just the surface content of the words.
   - Use `NEUTRAL` for narration and for dialogue with no discernible
     emotional charge.
   - Use only values from the fixed vocabulary (listed verbatim in the
     prompt).

4. `ElevenLabsProvider.synthesize()` accepts an optional
   `emotion: Optional[str]` parameter. When non-None and non-NEUTRAL, it
   prepends `[{emotion.lower()}]` to the text before the API call.
   Example: `emotion="ANGRY"` → `"[angry] I told you never to return!"`.

5. The ElevenLabs model is switched from `eleven_multilingual_v2` to
   `eleven_v3` in `ElevenLabsProvider`.
   Voice settings for emotional segments (emotion not None and not
   NEUTRAL):
   - `stability=0.35` — wider emotional range
   - `style=0.40` — amplify speaker character
   - `similarity_boost=0.75`
   - `use_speaker_boost=True`

   Voice settings for neutral/narration segments:
   - `stability=0.65` — controlled, consistent narrator delivery
   - `style=0.05`
   - `similarity_boost=0.75`
   - `use_speaker_boost=True`

6. `TTSOrchestrator.synthesize_chapter()` passes `segment.emotion` down
   to `ElevenLabsProvider.synthesize()` for each segment.

7. `output.json` (and `tts_output.json`) include the `emotion` field on
   every segment so the full pipeline output is inspectable.

8. `make verify` runs end-to-end on 3 chapters and the resulting
   `output.json` shows non-NEUTRAL emotion tags on at least some
   dialogue segments.

9. All existing tests pass. New unit tests cover:
   - `EmotionTag` enum values are exactly the 10 listed above
   - `Segment` round-trips `emotion` through `to_dict` / `from_dict`
   - `ElevenLabsProvider.synthesize()` prepends the tag when emotion is
     non-None and non-NEUTRAL; does not prepend for NEUTRAL or None
   - `AISectionParser` prompt string contains all 10 emotion labels

---

## Out of scope

- Per-character voice setting profiles (all characters share the two
  presets: emotional vs. neutral)
- Narrator emotion detection (narrator always uses neutral settings)
- Free-form emotion strings — only the 10-value enum is accepted
- Speech-to-speech or any audio input mechanism
- Streaming / real-time playback

---

## Key design decisions

### Fixed vocabulary, not free-form
A fixed enum means Sonnet's output is bounded and the TTS integration is
deterministic. Free-form tags risk Sonnet inventing labels that eleven_v3
doesn't respond to well. The 10-value vocabulary was derived empirically
from ElevenLabs' own documentation examples and covers the dramatic range
of classic prose fiction.

### Emotion on Segment, not synthesised inline
Storing `emotion` on the `Segment` model means it is serialised to JSON,
visible in `output.json`, unit-testable in isolation, and decoupled from
the TTS provider. The TTS provider is a thin transformer: it takes
`(text, voice_id, emotion)` and handles the inline-tag injection.

### Two voice-settings presets, not per-emotion tuning
Ten emotion values × N voices × two parameters = too many magic numbers.
Two presets (emotional / neutral) are sufficient to make a perceptible
difference while keeping the codebase simple and auditable. Finer tuning
can be a follow-up spec.

### Narrator always NEUTRAL
The narrator is a storytelling voice, not a character with inner states.
Applying emotion tags to narration produces jarring results (tested
manually). Narration segments always pass `emotion=None`.

### eleven_v3 replaces eleven_multilingual_v2
eleven_v3 is ElevenLabs' most emotionally expressive model and is
required for audio tags to work. eleven_multilingual_v2 silently ignores
inline tags. The model switch is the enabler for the entire feature.

---

## Files changed (expected)

| File | Change |
|---|---|
| `src/domain/models.py` | Add `EmotionTag` enum; add `emotion` field to `Segment` |
| `src/parsers/ai_section_parser.py` | Update prompt to output `emotion` field; parse it into `Segment` |
| `src/tts/elevenlabs_provider.py` | Add `emotion` param to `synthesize()`; switch to eleven_v3; add voice-settings presets |
| `src/tts/tts_provider.py` | Add `emotion` param to abstract `synthesize()` signature |
| `src/tts/tts_orchestrator.py` | Pass `segment.emotion` to provider |
| New test files alongside changed modules | TDD — tests written first |
