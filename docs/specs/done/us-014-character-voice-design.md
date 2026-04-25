# US-014 — Character Voice Design

## Goal

Use the `description` field populated by US-013 to generate a bespoke
ElevenLabs voice for each character via the Voice Design API. The result
is a `voice_id` that sounds like the character should sound — not just a
person of their age and gender.

---

## Dependency

**Requires US-013 to be complete.** This spec assumes every character with
sufficient text evidence already has a `description` field populated by the
AI section parser.

---

## Acceptance criteria

### 1. `Character.voice_design_prompt` field

`Character` in `src/domain/models.py` gains:

```python
voice_design_prompt: Optional[str] = None
```

This is the exact string sent to the Voice Design API. It is derived from
`description` (and `sex`/`age`) by the workflow — see AC2. It is persisted
in `book.json`.

### 2. `to_dict` / `from_dict` updated

`Character.to_dict()` and `Character.from_dict()` include
`voice_design_prompt`. Missing key defaults to `None`.

### 3. Workflow builds `voice_design_prompt` from `description`

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

### 4. `voice_designer.py` module

New `src/audio/voice_designer.py` exposes:

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

### 5. Voice assignment integration

`VoiceAssigner` (or wherever `voice_id` is assigned) is updated to check
`character.voice_design_prompt` before falling through to demographic
matching:

- `voice_design_prompt` set and no `voice_id` already assigned → call
  `design_voice()`, store returned `voice_id` on the character.
- Design API error or timeout → log `WARNING`, fall back to demographic
  match, do not re-raise.
- Designed voice IDs are stored in the character registry and reused
  across every beat for that `character_id`.

### 6. Output and observability

- `book.json` includes both `description` and `voice_design_prompt` on
  each character.
- Log at `INFO` level which characters received a designed voice and
  which fell back.
- `make verify` output includes both fields in `output.json`.

### 7. Tests

- Unit test: `Character` round-trips `voice_design_prompt` through
  `to_dict` / `from_dict`
- Unit test: `design_voice` calls create-previews then create-voice, in
  that order, and returns the `voice_id` from create-voice (mock
  ElevenLabs client — 1 mock)
- Unit test: workflow sets `voice_design_prompt` for a character with a
  long description and leaves it `None` for one with fewer than 10 words

---

## Out of scope

- Narrator voice design (narrator retains demographic assignment)
- Voice cloning from audio samples
- Per-chapter voice evolution (voice is fixed once designed)
- Cache invalidation if `description` changes between runs

---

## Key design decisions

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
| `src/domain/models.py` | Add `voice_design_prompt` field to `Character`; update `to_dict`/`from_dict` |
| `src/audio/voice_designer.py` | New module — ElevenLabs Voice Design API |
| `src/audio/voice_assigner.py` | Check `voice_design_prompt` before demographic match |
| `src/workflows/ai_project_gutenberg_workflow.py` | Build `voice_design_prompt` from `description` after all sections parsed |
| `src/audio/voice_designer_test.py` | New unit tests |
