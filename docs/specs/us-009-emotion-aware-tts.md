# US-009 — Emotion-Aware TTS

## Goal

Make characters sound the way they feel and stress the words the author
emphasised. Two expressive dimensions are added to `Segment`:

- **emotion** — the character's inner state at the time of speaking,
  detected by Sonnet 4.6 and rendered via ElevenLabs eleven_v3 inline
  audio tags.
- **emphases** — inline stress spans (from `<em>`, `<b>`, `<i>`,
  `<strong>` in the source HTML) mapped down from `Section` to each
  `Segment` and rendered as ALL-CAPS words in the synthesised text.

---

## Background / motivation

Today every segment is synthesised with flat voice settings and the
author's emphasis markup is discarded after HTML parsing. The pipeline
already knows _who_ speaks each line; this spec adds _how_ they feel and
_which words_ they stress.

The emotion "handshake": Sonnet 4.6 reads narrative context and picks
one of 10 fixed `EmotionTag` values per segment. ElevenLabs eleven_v3
receives that value as an inline audio tag (`[angry]`, `[whispering]`,
…) prepended to the text. Constraining both ends to the same enum makes
the contract reliable and testable — expanding to free-form is tracked
separately in US-010.

`EmphasisSpan` offsets currently live on `Section` but are never used
downstream. This spec threads them into `Segment` so the TTS layer can
act on them.

---

## Acceptance criteria

### Emotion

1. A new `EmotionTag` string enum exists in `src/domain/models.py` with
   exactly these values:

   ```
   NEUTRAL    EXCITED    ANGRY      SAD        FEARFUL
   WHISPERING CRYING     LAUGHING   STERN      GENTLE
   ```

2. `Segment` gains `emotion: Optional[EmotionTag] = None`.
   `Segment.to_dict()` / `from_dict()` serialise it as a nullable string.
   Default `None` is treated as `NEUTRAL` at synthesis time.

3. The AI segmentation prompt (`AISectionParser`) is updated to output
   an `emotion` field per segment alongside `speaker_id` and `type`. The
   prompt instructs the model to:
   - Pick the emotion that best fits the character's _inner state_ at
     the moment of speaking, not merely the surface words.
   - Use `NEUTRAL` for narration and for dialogue with no discernible
     emotional charge.
   - Only use values from the fixed 10-value vocabulary (listed verbatim
     in the prompt).

4. `ElevenLabsProvider.synthesize()` accepts
   `emotion: Optional[str] = None`. When non-None and not `"NEUTRAL"`,
   it prepends `[{emotion.lower()}] ` to the text before the API call.
   Example: `emotion="ANGRY"` → `"[angry] I told you never to return!"`.

5. ElevenLabs model switches from `eleven_multilingual_v2` to
   `eleven_v3`. Voice settings split into two presets:

   **Emotional** (emotion is not None and not NEUTRAL):
   - `stability=0.35`, `style=0.40`, `similarity_boost=0.75`,
     `use_speaker_boost=True`

   **Neutral / narration** (emotion is None or NEUTRAL):
   - `stability=0.65`, `style=0.05`, `similarity_boost=0.75`,
     `use_speaker_boost=True`

6. `TTSOrchestrator.synthesize_chapter()` passes `segment.emotion` to
   `ElevenLabsProvider.synthesize()` for every segment.

### Emphasis

7. `Segment` gains `emphases: list[EmphasisSpan] = field(default_factory=list)`.
   `Segment.to_dict()` / `from_dict()` serialise it as a list of
   `{start, end, kind}` dicts. Offsets are relative to `Segment.text`
   (not the parent `Section.text`).

8. When `AISectionParser` constructs `Segment` objects from a `Section`,
   it maps each `EmphasisSpan` from the section down to the segment
   whose text range contains it, adjusting the offset to be relative to
   the segment start. Spans that straddle a segment boundary are placed
   in the segment that contains the larger portion.

9. `ElevenLabsProvider.synthesize()` converts emphasis spans into
   ALL-CAPS words in the text before calling the API. Example: segment
   text `"I never wanted to go"` with emphasis on `"never"` (offsets
   2–7) → synthesised as `"I NEVER wanted to go"`. ALL-CAPS is the most
   universally reliable stress mechanism across TTS models; eleven_v3
   responds to it naturally.

10. `TTSOrchestrator.synthesize_chapter()` passes `segment.emphases` to
    `ElevenLabsProvider.synthesize()`.

### Output and verification

11. `output.json` includes both `emotion` and `emphases` on every
    segment.

12. `make verify` runs end-to-end on 3 chapters. The resulting
    `output.json` shows non-NEUTRAL emotion tags on at least some
    dialogue segments, and at least some segments carry non-empty
    `emphases` lists.

### Tests

13. All existing tests pass. New unit tests cover:
    - `Segment` round-trips `emotion` and `emphases` through
      `to_dict` / `from_dict`
    - `ElevenLabsProvider.synthesize()` prepends the audio tag when
      emotion is non-NEUTRAL; does not prepend for NEUTRAL or None
    - `ElevenLabsProvider.synthesize()` uppercases emphasized words
      correctly given a known text + EmphasisSpan list
    - `AISectionParser` prompt string contains all 10 emotion labels

---

## Out of scope

- Free-form emotion strings — tracked in **US-010**
- Per-character voice setting profiles
- Narrator emotion detection (narrator always uses neutral settings)
- Word-level emphasis inside narration-only sections that have no
  segments (pass-through sections)
- Speech-to-speech or audio input
- Streaming / real-time playback

---

## Key design decisions

### Emotion on Segment, not Section
`Section` is a structural unit (a paragraph). `Segment` is the unit of
speech — one character, one utterance. Emotion belongs to an utterance,
not a paragraph that may contain multiple speakers.

### Emphases mapped to Segment, not kept on Section
Currently `EmphasisSpan` offsets sit on `Section` and die there — the
TTS layer never sees them. Threading them into `Segment` with re-based
offsets means the TTS provider receives everything it needs in one
object: text, voice ID, emotion, emphases. Nothing is looked up from
parent objects at synthesis time.

### ALL-CAPS for emphasis, not `*word*` markdown
eleven_v3 audio tags (`[tag]`) are passage-level, not word-level. SSML
is not supported. `*word*` markdown behaviour is undocumented and
untested for eleven_v3. ALL-CAPS is universally understood by TTS
engines as a stress signal and produces reliable results without
model-specific behaviour.

### Fixed 10-value enum (expand in US-010)
A fixed enum bounds Sonnet's output and makes the eleven_v3 contract
deterministic. Free-form tags are possible with eleven_v3 but introduce
hallucination risk on the Sonnet side. See US-010 for the planned
expansion.

### Two voice-settings presets
Ten emotion values × N voices × tunable parameters = unmaintainable
magic-number soup. Two presets (emotional / neutral) produce a
perceptible difference while keeping the codebase auditable.

### Narrator always NEUTRAL
The narrator is a storytelling voice, not a character with an inner
state. Applying emotion tags to narration produces jarring results.
Narration segments always pass `emotion=None`.

---

## Files changed (expected)

| File | Change |
|---|---|
| `src/domain/models.py` | Add `EmotionTag` enum; add `emotion` and `emphases` fields to `Segment` |
| `src/parsers/ai_section_parser.py` | Output `emotion` per segment; map `Section.emphases` → `Segment.emphases` |
| `src/tts/tts_provider.py` | Add `emotion` and `emphases` params to abstract `synthesize()` |
| `src/tts/elevenlabs_provider.py` | Add params; switch to eleven_v3; presets; ALL-CAPS emphasis rendering |
| `src/tts/tts_orchestrator.py` | Pass `segment.emotion` and `segment.emphases` to provider |
| New test files alongside changed modules | TDD — tests written first |
