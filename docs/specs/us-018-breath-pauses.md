# US-018 — Breath Pauses in Long Segments

## Goal

Insert natural breath pauses within long TTS segments by splitting them
at sentence boundaries and inserting a short silence between sub-parts,
so that extended speeches don't sound like a single breathless recitation.

---

## Background / motivation

Segments with several hundred characters of continuous dialogue or
narration are synthesised as a single eleven_v3 API call. The model
renders them fluently but without any perceptible breath intake, making
long passages feel robotic.

Human speakers naturally pause briefly at sentence boundaries within a
longer speech. Inserting a short silence (~120 ms) between sentences
within a long segment approximates this rhythm without any API changes or
dependency on undocumented ElevenLabs audio tags.

The approach is purely audio-layer: split the text at sentence boundaries
before synthesis, synthesise each sentence separately, then join the
resulting clips with a breath-length silence. No AI call is needed; no
new prompt changes are required.

---

## Acceptance criteria

1. `TTSOrchestrator` (or a new `SegmentSplitter` helper in `src/tts/`)
   splits any segment whose text exceeds `breath_split_threshold_chars:
   int = 200` into sub-segments at sentence boundaries (`.`, `?`, `!`
   followed by a space or end-of-string).

2. Each sub-segment is synthesised as a separate API call with the same
   `voice_id` and `emotion` as the parent segment.

3. A silence clip of `breath_pause_ms: int = 120` is inserted between
   consecutive sub-segment clips (same mechanism as US-017 silence clips).

4. Sub-segments shorter than 10 characters (e.g. a lone `"Yes."`) are
   merged with the preceding sub-segment to avoid trivially short API
   calls.

5. Segments at or below `breath_split_threshold_chars` are synthesised
   as a single call — no change to existing behaviour.

6. The chapter-level segment count in logs reflects the original segment
   count (before splitting), so that log output stays meaningful.

7. Unit tests cover:
   - A 250-char segment is split into multiple sub-segments.
   - Each sub-segment carries the parent's `voice_id` and `emotion`.
   - A short trailing fragment (<10 chars) is merged with its predecessor.
   - A segment at exactly the threshold is not split.
   - A segment below the threshold is not split.

---

## Out of scope

- Splitting at commas or semicolons (sentence boundaries are sufficient
  and less likely to produce awkward micro-clips).
- Using ElevenLabs `[inhales]` or `[breathes]` audio tags — these are
  undocumented for eleven_v3 and behaviour is undefined.
- Varying the breath pause duration by emotion.

---

## Key design decisions

### Sentence split, not comma split
Comma-splitting produces clips as short as 3–4 words, which causes
audible inconsistency in voice rendering (eleven_v3 performs worse on
very short inputs). Sentence boundaries produce sub-segments of at
least one full clause.

### 200-char threshold
At typical English reading pace (~15 chars/second synthesised), 200
characters is roughly 13 seconds of audio — long enough to warrant a
breath, short enough that most dialogue lines are unaffected.

### Audio-only, no prompt changes
Splitting happens after segmentation, in the TTS layer. This keeps the
domain model and AI parser unchanged and makes the feature independently
testable.

---

## Files changed (expected)

| File | Change |
|---|---|
| `src/tts/tts_orchestrator.py` | Split long segments before synthesis loop; insert breath silences |
| `src/tts/tts_orchestrator_test.py` | Tests for split logic and silence insertion |
