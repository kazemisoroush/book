# US-019 — TTS Context and Expressiveness

## Problem

Listening to the generated audiobook reveals four quality issues:

1. **Character voices sound robotic** — each segment is synthesized as a cold
   start with no awareness of what came before or after. The model picks an
   arbitrary pitch, energy, and cadence every time.
2. **Emotions feel superficial** — the emotion tag (`[sarcastic]`, `[angry]`)
   is prepended but the voice settings are a binary switch (emotional vs
   neutral). "Mildly curious" and "screaming in rage" get identical
   `stability=0.35, style=0.40`. The emotions are not baked into the delivery.
3. **Voices don't follow the storyline** — a line after a dramatic revelation
   sounds the same as one after a quiet moment. There is zero narrative
   continuity between segments.
4. **Only the narrator sounds good** — because it doesn't need emotional range,
   the stable narrator preset works well. Character voices suffer most.

The root cause is that every `client.text_to_speech.convert()` call is made
in complete isolation: no `previous_text`, no `next_text`, no
`previous_request_ids`, and only two static voice-settings presets.

---

## Goal

Make character voices sound natural, emotionally grounded, and connected to
the narrative by using ElevenLabs API features that are available today but
not yet wired in.

---

## Potential fixes (prioritised)

### Fix 1 — `previous_text` / `next_text` context (highest impact)

The `client.text_to_speech.convert()` call already accepts two optional
string parameters we are not passing:

- **`previous_text`**: text that came before the current segment. Helps the
  model match prosody — how to *begin* the segment given what preceded it.
- **`next_text`**: text that comes after. Helps the model know how to *end*
  the segment — whether the thought continues or terminates.

This directly fixes problems #1 and #3. Each segment is no longer a cold
start; the model hears the narrative context and adjusts intonation
accordingly.

**Changes required**:

| File | Change |
|---|---|
| `src/tts/tts_provider.py` | Add `previous_text` and `next_text` optional params to `synthesize()` |
| `src/tts/elevenlabs_provider.py` | Pass them through to `client.text_to_speech.convert()` |
| `src/tts/audio_orchestrator.py` | In `_synthesise_segments`, look up adjacent segment text and pass it |

### Fix 2 — `previous_request_ids` chaining (high impact)

The API accepts up to 3 request IDs from prior same-voice generations via
`previous_request_ids`. This provides *acoustic* continuity — the model
matches pitch baseline, speaking rate, and energy to what it actually
produced before (not just what the text says).

**Caveat**: only works for consecutive segments using the **same voice**.
Requires maintaining a per-voice sliding window of the last 1–3 request IDs.

**Changes required**:

| File | Change |
|---|---|
| `src/tts/tts_provider.py` | Add `previous_request_ids` param; return request ID from `synthesize()` |
| `src/tts/elevenlabs_provider.py` | Pass `previous_request_ids` to SDK; extract request ID from response |
| `src/tts/audio_orchestrator.py` | Maintain per-voice request ID window; pass to each `synthesize()` call |

### Fix 3 — Graduated voice settings (medium impact)

Replace the binary emotional/neutral preset with a 4–5 tier system that maps
emotion intensity to progressively more expressive settings:

| Tier | Example emotions | stability | style | speed |
|---|---|---|---|---|
| neutral | narration, neutral | 0.65 | 0.05 | 1.0 |
| mild | curious, thoughtful, calm | 0.50 | 0.20 | 1.0 |
| moderate | angry, sad, happy, excited | 0.35 | 0.40 | 1.0 |
| intense | screaming, sobbing, furious, ecstatic | 0.25 | 0.60 | 1.05 |
| whispered | whispered, intimate, hushed | 0.45 | 0.30 | 0.90 |

This fixes problem #2: emotions will be proportional to their intensity
instead of one-size-fits-all.

**Changes required**:

| File | Change |
|---|---|
| `src/tts/elevenlabs_provider.py` | Replace binary preset with tier lookup; add `speed` param to SDK call |

### Fix 4 — Richer expressiveness via aggressive segment splitting (medium impact)

**Revised approach**: The original plan called for inline audio tags
(`[voice rising]`, ALL-CAPS emphasis) which require the `eleven_v3` model.
Since the project uses `eleven_multilingual_v2` (which supports
`previous_text`/`next_text` context but not inline tags), Fix 4 was
revised to achieve the same expressiveness goal through prompt improvements.

The AI segmentation prompt now:
- Splits more aggressively at emotional inflection points (any tonal shift,
  not just "significant" ones)
- Encourages specific, nuanced emotion labels (e.g. "frustrated", "seething",
  "wistful", "hesitant") over generic ones (e.g. "angry", "sad")
- Guides the LLM to split at natural vocal shift points within a single
  utterance (e.g. a character starts calm and becomes agitated)

Each sub-segment gets its own voice settings (stability/style/speed) from
the LLM (Fix 3), and Fixes 1+2 smooth transitions between segments via
`previous_text`/`next_text` and `previous_request_ids`.

ElevenLabs bills per character, not per API call, so more segments do not
increase cost.

**Changes required**:

| File | Change |
|---|---|
| `src/parsers/ai_section_parser.py` | Improve emotion instruction in prompt: aggressive splitting, nuanced labels, mid-utterance vocal shift guidance |

---

## Recommended implementation order

1. **Fix 1** — `previous_text` / `next_text`. Smallest change, biggest
   improvement. Can be shipped and tested independently.
2. **Fix 3** — Graduated voice settings. Small, self-contained change to
   `elevenlabs_provider.py`. Pairs well with Fix 1.
3. **Fix 2** — Request ID chaining. Medium effort, requires understanding
   SDK response format. Ship after Fix 1 is validated.
4. **Fix 4** — Richer inline tags. Requires AI prompt changes and
   re-parsing (cache bust). Ship last.

---

## Design note — context resolution as a separate concern

As more context sources are added (Fix 1: text context, Fix 2: request ID
chaining, US-020: scene modifiers), the logic for "what context does this
segment need?" should be extracted from `AudioOrchestrator._synthesise_segments`
into a dedicated `SegmentContextResolver` (or similar). This keeps the
orchestrator focused on file I/O and sequencing, and makes context resolution
independently testable. Fix 1 is small enough to inline; extract before Fix 2.

---

## Out of scope

- Switching to the ElevenLabs Projects/Studio API (overlaps with existing
  architecture; less control).
- SSML support (ElevenLabs does not support SSML).
- Dubbing API (designed for video, not audiobooks).
- Model changes (currently on `eleven_multilingual_v2` for context param support).
- Pronunciation dictionaries (useful for fantasy/sci-fi, not the current
  problem).
