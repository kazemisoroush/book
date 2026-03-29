# US-009 — Emotion-Aware TTS

## Goal

Make characters sound the way they feel, and stress the words the author
emphasised. Two expressive dimensions reach the TTS layer:

- **Emphasis** — words the author marked with `<em>`, `<b>`, `<strong>`,
  or `<i>` are converted to ALL-CAPS at HTML parse time. They flow
  into `Segment.text` naturally and ElevenLabs eleven_v3 stresses
  them automatically.

- **Emotion** — the character's inner state at the time of speaking,
  assigned by the AI during segmentation and rendered via eleven_v3
  inline audio tags (`[angry]`, `[whispering]`, …).

---

## Background / motivation

Today every segment is synthesised with flat voice settings and the
author's emphasis markup is discarded after HTML parsing. The pipeline
already knows _who_ speaks each line; this spec adds _how_ they feel
and _which words_ they stress.

### Two signals, two strategies

| Signal | Source | Where resolved | How rendered |
|--------|--------|----------------|--------------|
| Emphasis | HTML markup (`<em>`, `<b>`, …) | HTML parser | ALL-CAPS words in text |
| Emotion | Narrative context | AI segmentation | Inline audio tag prepended to text |

Emphasis is structural and deterministic — the author already decided
which words to stress; the parser just converts the encoding. Emotion is
semantic — the AI reads narrative context and picks the feeling.

Keeping these two paths separate avoids offset re-basing: there is no
`Segment.emphases` structure, no character-offset arithmetic after
model calls, and no fragile mapping across parser boundaries.

---

## Acceptance criteria

### 1 — Emphasis pre-processing in the HTML parser

`src/parsers/html_content_parser.py` (or wherever `Section.text` is
built from HTML) converts inline emphasis elements to ALL-CAPS **before**
any other processing:

- `<em>word</em>` → `WORD`
- `<b>word</b>` → `WORD`
- `<strong>word</strong>` → `WORD`
- `<i>word</i>` → `WORD`

Multi-word spans are uppercased in their entirety:
`<em>never wanted to go</em>` → `NEVER WANTED TO GO`.

`EmphasisSpan` is retained on `Section` as metadata for `output.json`,
but it is **not** mapped into `Segment` and is **not** used by the TTS
layer. The TTS path relies exclusively on ALL-CAPS text.

### 2 — EmotionTag enum

A new `EmotionTag` string enum in `src/domain/models.py` with exactly
these values:

```
NEUTRAL    EXCITED    ANGRY      SAD        FEARFUL
WHISPERING CRYING     LAUGHING   STERN      GENTLE
```

### 3 — Emotion field on Segment

`Segment` gains `emotion: Optional[EmotionTag] = None`.
`Segment.to_dict()` / `from_dict()` serialise it as a nullable string.
Default `None` is treated as `NEUTRAL` at synthesis time.

### 4 — AI segmentation outputs emotion

The AI segmentation prompt (`AISectionParser`) is updated to output an
`emotion` field per segment alongside `speaker_id` and `type`:

```json
{"speaker_id": "mr_darcy", "type": "dialogue", "text": "…", "emotion": "STERN"}
```

The prompt instructs the model to:
- Pick the emotion that best fits the character's _inner state_ at the
  moment of speaking, not merely the surface words.
- Use `NEUTRAL` for all narration segments and for dialogue with no
  discernible emotional charge.
- Only use values from the fixed 10-value vocabulary (listed verbatim
  in the prompt).
- **Split an utterance into multiple segments if the emotional tone
  shifts significantly mid-utterance** — e.g. a line that starts
  controlled and ends in tears should produce two segments, not one.
  Do not split for minor fluctuations; only split when the dominant
  emotion clearly changes. Each resulting segment carries its own
  `emotion` value.

### 5 — ElevenLabs provider: inline audio tag

`ElevenLabsProvider.synthesize()` accepts `emotion: Optional[str] = None`.
When non-None and not `"NEUTRAL"`, it prepends `[{emotion.lower()}] `
to the text before the API call.

Example: `emotion="ANGRY"`, text `"I told you never to return!"` →
sent to eleven_v3 as `"[angry] I told you NEVER to return!"`.

(ALL-CAPS emphasis is already in the text; the audio tag is prepended
on top.)

### 6 — ElevenLabs model and voice presets

Model switches from `eleven_multilingual_v2` to `eleven_v3`.
Voice settings use two presets:

**Emotional** (emotion is not None and not NEUTRAL):
- `stability=0.35`, `style=0.40`, `similarity_boost=0.75`,
  `use_speaker_boost=True`

**Neutral / narration** (emotion is None or NEUTRAL):
- `stability=0.65`, `style=0.05`, `similarity_boost=0.75`,
  `use_speaker_boost=True`

### 7 — Orchestrator wiring

`TTSOrchestrator.synthesize_chapter()` passes `segment.emotion` to
`ElevenLabsProvider.synthesize()` for every segment.

### 8 — Output and verification

`output.json` includes `emotion` on every segment.

`make verify` runs end-to-end on 3 chapters. The resulting `output.json`
shows non-NEUTRAL emotion tags on at least some dialogue segments.

### 9 — Tests

All existing tests pass. New unit tests cover:

- `Segment` round-trips `emotion` through `to_dict` / `from_dict`
- `ElevenLabsProvider.synthesize()` prepends the audio tag when emotion
  is non-NEUTRAL; does not prepend for NEUTRAL or None
- `ElevenLabsProvider.synthesize()` passes ALL-CAPS text unchanged (the
  provider does not uppercase — the parser already did)
- HTML parser outputs ALL-CAPS for `<em>`, `<b>`, `<strong>`, `<i>`
  content (no mock needed — pure string transformation)
- `AISectionParser` prompt string contains all 10 emotion labels

---

## Out of scope

- `Segment.emphases` / offset re-basing — eliminated in this spec
- AI-inferred word stress (words not marked in the HTML source)
- Free-form emotion strings — tracked in **US-010**
- Per-character voice setting profiles beyond the two presets
- Narrator emotion detection (narrator always NEUTRAL)
- Streaming / real-time playback

---

## Key design decisions

### Emphasis baked into text at parse time, not mapped via offsets

The original design stored `EmphasisSpan` objects with character offsets
on `Section`, then re-based them onto the appropriate `Segment` after
AI segmentation. This is fragile: the AI normalises whitespace, may
split tokens differently, and any drift silently produces wrong offsets.

Converting to ALL-CAPS during HTML parsing sidesteps all of this:
- Segments inherit ALL-CAPS words naturally — no offset arithmetic
- The TTS provider receives self-contained `Segment` objects with no
  parent lookups
- eleven_v3 responds to ALL-CAPS natively; no model-specific flag needed

`EmphasisSpan` is kept on `Section` solely for `output.json` visibility.

### Emotion on Segment, not Section

`Section` is a structural unit (a paragraph). `Segment` is the unit of
speech — one character, one utterance. A paragraph may contain multiple
speakers with different emotional states. Emotion belongs to the
utterance, not the paragraph.

Assigning emotion in the same AI call as segmentation means one
round-trip produces both structure and expressiveness. No second pass.

### Segment is the atomic unit of emotion — split rather than subdivide

Rather than introducing sub-segment emotion spans (which reintroduce the
offset-tracking complexity we eliminated for emphasis), the AI is
permitted to split a single utterance into multiple segments when
emotional tone shifts significantly mid-utterance. A line that begins
calm and ends in tears becomes two segments: one NEUTRAL, one CRYING.

This keeps the data model clean: every `Segment` has exactly one
`emotion`, and the TTS provider prepends exactly one audio tag per API
call. No offset arithmetic. No multi-tag strings.

### Fixed 10-value enum (expand in US-010)

A fixed enum bounds Sonnet's output and makes the eleven_v3 contract
deterministic. Free-form tags are possible with eleven_v3 but introduce
hallucination risk on the Sonnet side. See US-010 for the planned
expansion.

### Narrator always NEUTRAL

The narrator is a storytelling voice, not a character with an inner
state. Applying emotion tags to narration produces jarring results.
Narration segments always pass `emotion=None`.

### Two voice-settings presets

Ten emotion values × N voices × tunable parameters = unmaintainable
magic-number soup. Two presets (emotional / neutral) produce a
perceptible difference while keeping the codebase auditable.

---

## Files changed (expected)

| File | Change |
|---|---|
| `src/parsers/html_content_parser.py` | Convert inline emphasis tags → ALL-CAPS in section text |
| `src/domain/models.py` | Add `EmotionTag` enum; add `emotion` field to `Segment` |
| `src/parsers/ai_section_parser.py` | Output `emotion` per segment in the AI prompt and response parsing |
| `src/tts/tts_provider.py` | Add `emotion` param to abstract `synthesize()` |
| `src/tts/elevenlabs_provider.py` | Add `emotion` param; switch to eleven_v3; presets; prepend audio tag |
| `src/tts/tts_orchestrator.py` | Pass `segment.emotion` to provider |
| New test files alongside changed modules | TDD — tests written first |
