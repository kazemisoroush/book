# US-014 — Character Voice Design

## Goal

Give each named character a bespoke voice that matches their description
rather than a generic demographic assignment. When character enrichment
(US-003) has produced a physical and personality description for a
character, that description is passed to the ElevenLabs Voice Design API
to generate a custom voice. The result is a voice that sounds like the
character should sound, not just like a person of their age and gender.

---

## Background / motivation

Today, voice assignment is demographic: the AI derives sex and age from
the character registry, and `VoiceAssigner` picks the closest matching
preset voice. The voice fits the character's demographics but nothing
else — a gruff old villain and a kindly old mentor get voices from the
same pool.

ElevenLabs offers a Voice Design API that takes a text description of a
voice and generates a custom voice_id. A description such as
_"deep gravelly baritone, 60s, weathered, commanding, slight rasp"_
produces a voice designed specifically for that character. Once
generated, the voice_id is reused for every line that character speaks.

This spec covers character voice design as a standalone feature. It is
separate from cinematic casting (US-013), which matches characters to
voices resembling known actors from film adaptations.

---

## Acceptance criteria

1. `Character` in `src/domain/models.py` gains:

   ```python
   voice_design_prompt: Optional[str] = None
   ```

   This field holds the description text used to design the voice.
   It is populated by the AI workflow and persisted in `book.json`.

2. A `src/tts/voice_designer.py` module exposes:

   ```python
   def design_voice(description: str, character_name: str, client: ElevenLabs) -> str:
       """Create a voice from a text description.

       Calls ElevenLabs Voice Design API (POST /v1/text-to-voice/create-previews,
       then POST /v1/text-to-voice/create-voice) and returns the new voice_id.

       character_name is used as the voice label in ElevenLabs.
       """
   ```

   The API flow:
   - `POST /v1/text-to-voice/create-previews` with the description and
     `preview_text` set to a neutral sentence. Returns 3 preview options.
   - Select the first preview's `generated_voice_id`.
   - `POST /v1/text-to-voice/create-voice` with that `generated_voice_id`
     and `voice_name = character_name` to save it permanently.
   - Return the resulting `voice_id`.

3. The AI workflow (`ai_project_gutenberg_workflow.py`) builds a
   `voice_design_prompt` for each character that has a description:

   Template:
   ```
   {age_descriptor} {gender}, {physical_description}. {personality_note}.
   Speaking style: {speech_style}.
   ```

   If the character has insufficient description for a meaningful prompt
   (fewer than 10 words of enrichment), skip voice design for that
   character.

4. `VoiceAssigner` is updated to check `character.voice_design_prompt`
   before falling through to demographic matching:

   - If `voice_design_prompt` is set and no `voice_id` is already
     assigned: call `design_voice()`, store the returned `voice_id` on
     the character.
   - If voice design fails (API error, timeout), log a warning and fall
     back to demographic matching — never crash the pipeline.
   - Designed voices are stored in the character registry and reused
     across all segments with that `character_id`.

5. `make verify` output includes `voice_design_prompt` on enriched
   characters in `output.json`.

6. New unit tests cover:
   - `Character` round-trips `voice_design_prompt` through
     `to_dict` / `from_dict`
   - `design_voice` calls create-previews then create-voice in order
     (mock ElevenLabs client — 1 mock)

---

## Out of scope

- Narrator voice design (narrator retains demographic assignment)
- Voice cloning from audio samples
- Per-chapter voice evolution (character voices are fixed once designed)
- Regenerating a voice if the design prompt changes (requires cache
  invalidation logic — deferred)
- Cinematic casting (US-013) — that feature operates on a different
  trigger (recognised movie adaptations) and is independent

---

## Key design decisions

### Voice Design API over demographic matching
A designed voice is always more distinctive than a demographic pick.
The only risk is API latency: designing N voices adds N round-trips to
the workflow setup phase. This is acceptable because voice design runs
once per book, not once per segment.

### Fallback to demographic on any failure
Voice design failures must not block audio production. The fallback path
(demographic matching) already works; silence the error, log it, and
continue.

### Store voice_design_prompt in domain model
Persisting the prompt in `book.json` makes the voice reproducible and
auditable. If a character's description changes in a future re-run,
the prompt changes and a new voice would be designed.

### Select first preview
Choosing among 3 previews requires human judgement. For an automated
pipeline, the first preview is sufficient; a future interactive mode
could surface all three for manual selection.

---

## Files changed (expected)

| File | Change |
|---|---|
| `src/domain/models.py` | Add `voice_design_prompt` field to `Character` |
| `src/tts/voice_designer.py` | New module — ElevenLabs Voice Design API |
| `src/tts/voice_assigner.py` | Check `voice_design_prompt` before demographic match |
| `src/workflows/ai_project_gutenberg_workflow.py` | Build `voice_design_prompt` from character enrichment |
| `src/tts/voice_designer_test.py` | New unit tests |
