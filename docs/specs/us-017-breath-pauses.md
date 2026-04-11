# US-017 — Vocal Effects (Breaths, Coughs, Sighs, etc.)

## Goal

Enable the audiobook to include natural non-speech character sounds (breaths, coughs, sighs, gasps, laughter, etc.) by introducing a new `VOCAL_EFFECT` segment type. The AI parser detects moments where characters make these sounds and outputs dedicated segments with free-form text descriptions. The audio builder generates appropriate short audio clips for each vocal effect.

## Problem

Real human speech is punctuated by non-verbal sounds: a character might take a soft breath before a difficult confession, cough nervously during an interrogation, or sigh heavily with resignation. Currently, the audiobook has no way to represent or synthesize these moments. Long speeches sound unnaturally breathless, and emotional beats that depend on vocal sounds (sobbing, gasping, throat-clearing) are lost entirely.

The old breath-pause approach (splitting long segments at sentence boundaries and inserting silence) was a TTS-layer hack that only addressed the breathless-speech problem, not the broader need for character-driven vocal sounds.

## Acceptance criteria

1. `SegmentType` enum in `src/domain/models.py` gains a new value: `VOCAL_EFFECT = "vocal_effect"`.

2. The `Segment` dataclass already has all necessary fields:
   - `segment_type: SegmentType.VOCAL_EFFECT` to mark it as a vocal effect
   - `text: str` contains the free-form description (e.g., "soft breath intake", "dry persistent cough", "quiet nervous laughter")
   - `character_id: str` identifies which character makes the sound (so the audio builder can use their voice)

3. `AISectionParser` is updated to detect vocal effects during segmentation:
   - The AI prompt instructions in `src/parsers/prompt_builder.py` are extended to instruct the LLM to output `VOCAL_EFFECT` segments when appropriate.
   - The prompt explains: "When the narrative implies a character makes a non-speech vocal sound (breath, cough, sigh, gasp, laugh, sob, throat clear, sneeze, etc.), output a segment with `type: 'vocal_effect'`, `text` describing the sound in 1-5 words (e.g., 'soft breath intake', 'dry persistent cough'), and `speaker` set to the character making the sound."
   - The prompt emphasizes: "Only include vocal effects for sounds the **narrative explicitly implies** or describes. Do NOT invent sounds that are not textually supported."
   - Vocal effect segments appear in the timeline wherever the LLM determines they belong (typically between dialogue/narration segments).

4. `AISectionParser._parse_response()` correctly parses segments with `type: "vocal_effect"` into `Segment` objects with `segment_type=SegmentType.VOCAL_EFFECT`.

5. `TTSOrchestrator.synthesize_chapter()` handles `VOCAL_EFFECT` segments:
   - Generates short audio clips (1-3 seconds) for each vocal effect using the character's assigned voice.
   - The implementation uses TTS with special prompts (e.g., passing the description as emotion/text to ElevenLabs), or calls a future sound-effect provider.
   - If audio generation fails for a vocal effect, log a warning and insert 150ms of silence as a fallback (the audiobook must not crash).

6. Vocal effect segments are included in the `Book.to_dict()` serialization and correctly deserialized via `Book.from_dict()` (this already works since they are just `Segment` instances with a new `segment_type` value).

7. The old breath-pause splitting logic (if it exists in `TTSOrchestrator`) is removed entirely. Long segments are no longer split at sentence boundaries in the TTS layer.

8. Unit tests cover:
   - `SegmentType.VOCAL_EFFECT` is a valid enum value
   - `AISectionParser._parse_response()` correctly parses a segment with `"type": "vocal_effect"` into a `Segment` with `segment_type=SegmentType.VOCAL_EFFECT`
   - `TTSOrchestrator.synthesize_chapter()` skips TTS calls for `VOCAL_EFFECT` segments and either generates audio or inserts silence
   - `Segment.is_narratable` returns `False` for `VOCAL_EFFECT` segments (so they are not counted as narration or dialogue)
   - `Book.to_dict()` and `Book.from_dict()` round-trip a vocal effect segment correctly

## Out of scope

- Enumerating a fixed list of vocal effect types (descriptions are free-form text, chosen by the LLM)
- Training a dedicated vocal-effect synthesis model (initial implementation uses TTS or simple sound generation)
- Retroactively adding vocal effects to already-parsed books (requires re-parsing with `--reparse`)
- Configuring vocal effect volume or duration per segment (fixed at 1-3 seconds, normal volume)
- Handling ambient background sounds that are not character-driven (those belong in scene ambient audio, not vocal effects)

## Key design decisions

### Free-form descriptions, not enums

Vocal sounds have infinite variety ("sharp intake of breath" vs. "long slow exhale" vs. "shallow panting"). A fixed enum would either be too limited (missing nuances) or too large (hundreds of values). Free-form text lets the LLM describe exactly what the narrative implies, and the audio builder can interpret or approximate as needed.

### Vocal effects are their own segments

Rather than modifying existing dialogue/narration segments with metadata, vocal effects are independent segments in the timeline. This makes them easy to render, skip, or replace without affecting surrounding speech. It also keeps the domain model simple: every segment has exactly one purpose (speech or sound).

### AI detection, not post-processing

Vocal effects are detected during AI segmentation, not added later. The LLM has full narrative context (character emotions, scene descriptions, dialogue tags like "she sighed" or "he gasped") and can infer appropriate moments. Post-processing in the TTS layer would have no access to this context.

### `is_narratable` returns False

Vocal effects are not "narration" or "dialogue" — they are non-speech audio. `Segment.is_narratable` returns `False` for `VOCAL_EFFECT` segments so they are filtered out of caches and logs that count speakable content. They are rendered during audio assembly but not treated as text-to-speech material.

### Fallback to silence on failure

If vocal effect audio generation fails (API error, unsupported description, etc.), the audio builder inserts a short silence (150ms) and logs a warning. The audiobook must not crash due to a failed sound effect. This graceful degradation ensures robustness.

## Files changed (expected)

| File | Change |
|---|---|
| `src/domain/models.py` | Add `VOCAL_EFFECT = "vocal_effect"` to `SegmentType` enum; update `is_narratable` property to exclude `VOCAL_EFFECT` |
| `src/parsers/prompt_builder.py` | Add vocal effect instructions to the AI prompt (detect non-speech character sounds, output free-form descriptions) |
| `src/parsers/ai_section_parser.py` | Update `_parse_response()` to handle `"type": "vocal_effect"` in JSON (already works generically, but verify) |
| `src/tts/tts_orchestrator.py` | Handle `VOCAL_EFFECT` segments: generate short audio clips or insert silence fallback |
| `src/domain/models_test.py` | Test `SegmentType.VOCAL_EFFECT` exists and `is_narratable` returns `False` for vocal effect segments |
| `src/parsers/ai_section_parser_test.py` | Test parsing `"type": "vocal_effect"` into `Segment` with correct `segment_type` |
| `src/tts/tts_orchestrator_test.py` | Test `TTSOrchestrator` skips TTS for `VOCAL_EFFECT` and inserts silence or generates audio |

## Relationship to other specs

- **US-023 (Cinematic Sound Effects)**: Vocal effects are character-driven (breaths, coughs) while cinematic SFX are diegetic scene sounds (knocking, footsteps). Both are detected by the AI parser but rendered differently. Vocal effects use the character's voice; cinematic SFX use a sound-effect provider.
- **US-016 (Inter-Segment Silence)**: Vocal effects are segments in the timeline, so they naturally participate in silence insertion rules (a breath gets silence before/after it just like dialogue).
- **Old breath-pause splitting logic**: Completely replaced by this spec. If any sentence-boundary splitting code exists in `TTSOrchestrator`, it is removed.

## Implementation notes

### Prompt wording

The AI prompt must be clear that vocal effects are **only** for non-speech character sounds, not ambient noise or visual actions. Suggested phrasing:

> When the narrative implies a character makes a **non-speech vocal sound** (breath intake/exhale, cough, sigh, gasp, laugh, sob, throat clear, sneeze, groan, etc.), output a segment with `type: "vocal_effect"`, `text` describing the sound in 1-5 words (e.g., "soft breath intake", "dry persistent cough", "quiet nervous laughter"), and `speaker` set to the character making the sound. Only include vocal effects for sounds the narrative **explicitly implies** or describes. Do NOT invent sounds that are not textually supported.

### TTS rendering options

The initial implementation can:
1. Call `TTSProvider.synthesize(text=description, voice_id=character_voice_id, emotion="neutral")` with a very short `max_length` (1-2 seconds). This may produce intelligible speech of the description, or a vocal approximation.
2. Call a dedicated sound-effect API (e.g., ElevenLabs Sound Effects) with the description.
3. Insert 150ms of silence as a placeholder (fallback if no provider is available).

The spec does not mandate a specific implementation — just that vocal effects are handled non-crashing and logged.

### JSON schema update

The existing prompt already shows JSON examples with fields like `type`, `text`, `speaker`. Adding `"vocal_effect"` as a valid `type` value is sufficient. The LLM will follow the example structure.

### Backward compatibility

Existing parsed books (without `VOCAL_EFFECT` segments) continue to work. New parsings will include vocal effects if the narrative supports them. No migration is needed.
