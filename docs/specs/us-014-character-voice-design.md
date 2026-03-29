# US-014 — Character Voice Design

## Goal

Extract a voice-relevant description for every named character during AI
parsing, then use that description with the ElevenLabs Voice Design API to
generate a bespoke voice for each character. The result is a voice that
sounds like the character should sound — not just a person of their age
and gender.

---

## How this is different from US-013

| | US-013 (backlog / stretch) | US-014 (this spec) |
|---|---|---|
| Trigger | Book is a known movie/TV adaptation | Any book with named characters |
| Voice origin | Searches public Voice Library for existing voice | **Generates** a brand-new voice via Voice Design API |
| What guides selection | Actor's vocal profile (film cast) | Character's own description from the book text |
| API used | `GET /v1/shared-voices` | `POST /v1/text-to-voice/create-previews` + `create-voice` |

---

## Background / motivation

Today, voice assignment is demographic: the AI extracts `sex` and `age`
for each character, and `VoiceAssigner` picks the closest matching preset
voice. The voice fits demographics but nothing else — a gruff old villain
and a kindly old mentor draw from the same pool.

ElevenLabs offers a Voice Design API: give it a text description such as
_"deep gravelly baritone, 60s, weathered, commanding, slight rasp"_ and
it generates a `voice_id` specifically designed for that profile. Once
created the voice is reused for every line that character speaks.

**Current gap:** `Character.description` exists as a field in the model
but the AI section parser never asks the model to populate it — today it
is always `None` in practice. This spec adds description extraction to
the parser prompt as step one, then uses that description to drive Voice
Design as step two.

---

## Acceptance criteria

### 1. AI section parser extracts `description` for new characters

Update the `new_characters` JSON schema in `AISectionParser`'s prompt
(`src/parsers/ai_section_parser.py`) to include an optional `description`
field:

```json
{
  "character_id": "hagrid",
  "name": "Rubeus Hagrid",
  "sex": "male",
  "age": "adult",
  "description": "booming bass voice, thick West Country accent, warm and boisterous, giant of a man"
}
```

Prompt instruction to add:

> For each new character, add a `description`: 1–2 sentences describing
> their voice and manner of speaking — include vocal quality (pitch,
> roughness, warmth), accent if evident, and personality as expressed in
> speech. If nothing can be inferred from context, omit the field entirely
> (do not guess).

Existing characters already in the registry are **not** re-enriched in
this spec — only newly discovered characters receive `description`.

### 2. `Character.voice_design_prompt` field

`Character` in `src/domain/models.py` gains:

```python
voice_design_prompt: Optional[str] = None
```

This is the exact string sent to the Voice Design API. It is derived from
`description` (and `sex`/`age`) by the workflow — see AC4. It is
persisted in `book.json`.

### 3. `to_dict` / `from_dict` updated

`Character.to_dict()` and `Character.from_dict()` include
`voice_design_prompt`. Missing key defaults to `None`.

### 4. Workflow builds `voice_design_prompt` from `description`

In `ai_project_gutenberg_workflow.py`, after all sections are parsed,
iterate the character registry and for each non-narrator character where
`description` is set and has ≥ 10 words:

Compose `voice_design_prompt` from:

```
{age} {sex}, {description}.
```

Examples:
- `"adult male, booming bass voice, thick West Country accent, warm and boisterous, giant of a man."`
- `"young female, bright clear soprano, quick and precise speech, slight nervous energy."`

If `description` is `None` or fewer than 10 words, leave
`voice_design_prompt = None` (character falls through to demographic
assignment).

### 5. `voice_designer.py` module

New `src/tts/voice_designer.py` exposes:

```python
def design_voice(description: str, character_name: str, client: ElevenLabs) -> str:
    """
    Generate a custom ElevenLabs voice from a text description.
    Returns the permanent voice_id.

    API flow:
    1. POST /v1/text-to-voice/create-previews  →  3 preview options
    2. Take first preview's generated_voice_id
    3. POST /v1/text-to-voice/create-voice     →  permanent voice_id
    """
```

`preview_text` in step 1 is a fixed neutral sentence (e.g. `"The morning
light filtered through the window as she poured the tea."`). Using a
fixed sentence keeps tests deterministic and avoids sending character
dialogue to the previews endpoint unnecessarily.

### 6. Voice assignment integration

`VoiceAssigner` (or wherever voice_id is assigned) is updated to check
`character.voice_design_prompt` before falling through to demographic
matching:

- `voice_design_prompt` set and no `voice_id` already assigned → call
  `design_voice()`, store returned `voice_id` on the character.
- Design API error or timeout → log `WARNING`, fall back to demographic
  match, do not re-raise.
- Designed voice IDs are stored in the character registry and reused
  across every segment for that `character_id`.

### 7. Output and observability

- `book.json` includes both `description` and `voice_design_prompt` on
  each character.
- Log at `INFO` level which characters received a designed voice and
  which fell back.
- `make verify` output includes both fields in `output.json`.

### 8. Tests

- Unit test: `AISectionParser` passes `description` through when present
  in the AI response (mock AI provider — 1 mock)
- Unit test: `Character` round-trips `voice_design_prompt` through
  `to_dict` / `from_dict`
- Unit test: `design_voice` calls create-previews then create-voice, in
  that order, and returns the `voice_id` from create-voice (mock
  ElevenLabs client — 1 mock)
- Unit test: workflow sets `voice_design_prompt` for a character with a
  long description and leaves it `None` for one with fewer than 10 words

---

## Out of scope

- Re-enriching characters already in the registry (only new characters
  get `description` extracted)
- Narrator voice design (narrator retains demographic assignment)
- Voice cloning from audio samples
- Per-chapter voice evolution (voice is fixed once designed)
- Cache invalidation if `description` changes between runs
- Cinematic casting (US-013) — different trigger, different API, kept
  in backlog

---

## Key design decisions

### Description extraction in the parser, not a separate AI call
Adding `description` to the existing `new_characters` JSON in the section
parser prompt costs nothing beyond a few extra tokens per new character.
A separate enrichment pass would double the AI calls. The parser already
sees the full context needed to infer vocal qualities.

### `voice_design_prompt` is a derived field, not the raw description
`description` is what the AI observed ("booming bass voice, thick West
Country accent"). `voice_design_prompt` is the formatted string actually
sent to ElevenLabs ("adult male, booming bass voice, thick West Country
accent"). Keeping them separate means `description` is readable in
`book.json` without Voice Design API formatting concerns baked in.

### 10-word minimum on description
A description of fewer than 10 words (e.g. "male voice") gives Voice
Design nothing useful to work with. Demographic fallback will produce a
better result than a vague prompt.

### Fixed `preview_text`
Choosing among 3 previews requires human judgement. For an automated
pipeline, the first preview is sufficient. The fixed preview sentence
keeps synthesis deterministic across runs.

### Fallback on any API error
Voice design failures must never block audio production. The demographic
fallback already works; log and continue.

---

## Files expected to change

| File | Change |
|---|---|
| `src/parsers/ai_section_parser.py` | Add `description` to `new_characters` prompt schema and parsing |
| `src/domain/models.py` | Add `voice_design_prompt` field to `Character`; update `to_dict`/`from_dict` |
| `src/tts/voice_designer.py` | New module — ElevenLabs Voice Design API |
| `src/tts/voice_assigner.py` | Check `voice_design_prompt` before demographic match |
| `src/workflows/ai_project_gutenberg_workflow.py` | Build `voice_design_prompt` from `description` after parsing |
| `src/parsers/ai_section_parser_test.py` | Unit test for `description` passthrough |
| `src/tts/voice_designer_test.py` | New unit tests |
