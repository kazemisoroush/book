# US-010 — Free-Form Emotion Tags

## Goal

Replace the fixed 10-value `EmotionTag` enum introduced in US-009 with
an open-ended string that lets Sonnet 4.6 express the full natural
vocabulary of ElevenLabs eleven_v3 audio tags. This unlocks finer
emotional nuance without the artificial constraint of a hard-coded list.

---

## Background / motivation

US-009 ships a fixed enum (`NEUTRAL EXCITED ANGRY SAD FEARFUL
WHISPERING CRYING LAUGHING STERN GENTLE`) to keep the first version
safe and testable. ElevenLabs eleven_v3 actually accepts any 1–2 word
natural-language audio tag with no predefined limit. Sonnet 4.6 is
fully capable of inferring richer descriptors from literary context:
`breathless`, `sarcastic`, `pleading`, `bitter`, `cold`, `urgent`,
`trembling`, `mournful`, `horrified`, `bewildered`.

Keeping the enum forever means we leave expressive range on the table.
This spec unlocks that range once US-009 is stable and the basic emotion
pipeline is proven in production.

---

## Acceptance criteria

1. `EmotionTag` enum is removed. `Segment.emotion` changes type from
   `Optional[EmotionTag]` to `Optional[str]`. All serialisation
   (`to_dict` / `from_dict`) continues to work unchanged (it was already
   storing the string value).

2. A module-level constant `VERIFIED_EMOTION_TAGS: frozenset[str]` is
   defined in `src/domain/models.py`. It contains the 10 original enum
   values plus the extended vocabulary confirmed to work with eleven_v3:

   ```
   # Original 10
   neutral  excited  angry    sad      fearful
   whispering  crying  laughing  stern   gentle
   # Extended
   breathless  sarcastic  pleading  bitter  cold
   urgent  trembling  mournful  horrified  bewildered
   shouting  nervous  surprised  disgusted  happy
   ```

   (All lowercase — the canonical form matches what is sent to eleven_v3.)

3. The AI segmentation prompt (`AISectionParser`) is updated to instruct
   Sonnet to output any concise emotional descriptor (1–2 words,
   lowercase) that best fits the moment, not just the original 10. The
   `VERIFIED_EMOTION_TAGS` list is shown as examples, not as a hard
   constraint.

4. `ElevenLabsProvider.synthesize()` validates the received emotion
   string:
   - If it is in `VERIFIED_EMOTION_TAGS` (case-insensitive) → use it
     as-is (lowercased).
   - If it is an unknown string → log a `structlog` warning
     (`emotion_tag_unknown`) and fall back to no tag (treat as neutral).
   - This prevents unknown Sonnet output from being forwarded to
     eleven_v3 where the behaviour is undefined.

5. The emotional voice-settings preset (non-neutral) continues to apply
   for any non-None, non-`"neutral"` tag — the preset is tag-agnostic.

6. All existing US-009 tests that reference `EmotionTag` enum values are
   updated to use string literals. No new behaviour is broken.

7. New unit tests cover:
   - `VERIFIED_EMOTION_TAGS` contains all 10 original values
   - Unknown tag triggers the fallback + warning log
   - Known extended tag (e.g. `"breathless"`) is passed through without
     warning

---

## Out of scope

- Per-tag voice setting tuning (each tag still uses emotional or neutral
  preset)
- Automatic discovery of new eleven_v3 tags (the verified list is
  manually curated and updated)
- Multi-word tags longer than 2 words

---

## Key design decisions

### Validated passthrough, not open trust
Passing Sonnet's raw output directly to eleven_v3 without validation
risks the model emitting multi-word or nonsensical tags that get
"spoken aloud" as text (eleven_v3 reads unknown tags as literal text if
it cannot interpret them). The `VERIFIED_EMOTION_TAGS` allowlist + warn-
and-fallback pattern keeps the failure mode safe and observable.

### Lowercase canonical form
eleven_v3 audio tags are case-sensitive (`[Angry]` may differ from
`[angry]`). Lowercasing everything before sending normalises both
Sonnet's output and the verified list to a single canonical form.

### `VERIFIED_EMOTION_TAGS` lives in `domain/`, not `tts/`
The tag vocabulary is a domain concept shared between the AI parser
(producer) and the TTS layer (consumer). Putting it in `domain/` avoids
a cross-layer import in the parser.

---

## Files changed (expected)

| File | Change |
|---|---|
| `src/domain/models.py` | Remove `EmotionTag` enum; change field type; add `VERIFIED_EMOTION_TAGS` |
| `src/parsers/ai_section_parser.py` | Update prompt to free-form guidance |
| `src/audio/elevenlabs_provider.py` | Add validation + warn-and-fallback logic |
| Updated test files | Replace enum refs with string literals; add validation tests |
