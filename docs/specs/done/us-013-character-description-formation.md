# US-013 — Character Description Formation

## Goal

Extract a voice-relevant description for every named character during AI
parsing, and progressively enrich it as the story reveals more about how
each character sounds and speaks. The result is a `description` field on
each character that captures vocal quality, accent, and speech personality
— ready to be used by US-014 to generate a bespoke voice.

---

## Background / motivation

Today, voice assignment is purely demographic: the AI extracts `sex` and
`age` for each character, and `VoiceAssigner` picks the closest preset.
A gruff old villain and a kindly old mentor draw from the same pool.

`Character.description` already exists as a field in the domain model but
the AI section parser never asks the model to populate it — today it is
always `None` in practice. This spec makes `description` meaningful by:

1. Asking the AI to extract vocal descriptions for new characters on first
   encounter.
2. Allowing the AI to refine that description as later sections reveal more
   about a character's voice, accent, or manner of speaking.

Voice design itself (using `description` to call the ElevenLabs Voice
Design API) is handled in US-014.

---

## Acceptance criteria

### 1. Parser extracts `description` for new characters

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

> **New characters:** For each new character, add a `description`: 1–2
> sentences describing their voice and manner of speaking — include vocal
> quality (pitch, roughness, warmth), accent if evident, and personality
> as expressed in speech. If nothing can be inferred from context, omit
> the field entirely (do not guess).

### 2. Parser progressively enriches descriptions for existing characters

The parser response also gains a `character_description_updates` array.
When the current section reveals meaningfully new vocal or speech
information about a character already in the registry, the AI may return a
refined description that supersedes the previous one:

```json
{
  "character_description_updates": [
    {
      "character_id": "hagrid",
      "description": "booming bass voice, thick West Country accent, warm and boisterous; voice trembles and cracks when distressed"
    }
  ]
}
```

The updated description is a **full replacement** — the AI synthesises the
old and new observations into one coherent sentence. If the section adds
nothing meaningful, the character is omitted from the array entirely.

To enable synthesis, the parser prompt must include the **current
`description`** for each character already in the registry (passed in the
existing-characters block). If a character has no description yet, omit
the field from that block.

Prompt instruction to add:

> **Existing characters:** If this section reveals meaningfully new
> information about how an existing character sounds or speaks, add an
> entry to `character_description_updates` with a revised `description`
> that synthesises what was known before with what is new. Only include
> entries where there is genuine new vocal information; omit the character
> otherwise.

### 3. Workflow applies description updates as sections are processed

In `ai_project_gutenberg_workflow.py`, after each section is parsed, if
the AI response includes `character_description_updates`, apply them
immediately to the in-memory character registry (overwriting the
character's `description` field). This means each subsequent section sees
the running accumulated description when its prompt is built.

### 4. Tests

- Unit test: `AISectionParser` passes `description` through for a new
  character when present in the AI response (mock AI provider — 1 mock)
- Unit test: `AISectionParser` applies `character_description_updates` —
  when the AI response includes an update for an existing character, the
  character's description in the registry is replaced with the new value
  (mock AI provider — 1 mock)
- Unit test: workflow applies a `character_description_updates` entry to
  the registry immediately after the section is parsed, so the next
  section's prompt receives the updated description

---

## Out of scope

- Narrator description (narrator retains demographic assignment)
- Using `description` to generate a voice (US-014)
- Cache invalidation if `description` changes between runs

---

## Key design decisions

### Description extraction in the parser, not a separate AI call
Adding `description` to the existing `new_characters` JSON costs nothing
beyond a few extra tokens per new character. A separate enrichment pass
would double AI calls. The parser already sees the full context needed to
infer vocal qualities.

### Progressive enrichment via full replacement
Rather than appending fragments, the AI is asked to synthesise a complete
updated sentence each time. This keeps `description` readable as a single
coherent statement and avoids cumulative redundancy.

### Current description passed back in the prompt
The AI cannot improve a description it cannot see. Including the current
`description` in the existing-character block for each section costs a
small number of tokens and enables the AI to write a genuinely improved
synthesis rather than a disconnected addendum.

---

## Files expected to change

| File | Change |
|---|---|
| `src/parsers/ai_section_parser.py` | Add `description` to `new_characters` schema; add `character_description_updates` to response parsing; include current description in existing-character block |
| `src/workflows/ai_project_gutenberg_workflow.py` | Apply `character_description_updates` to registry after each section |
| `src/parsers/ai_section_parser_test.py` | Unit tests for description passthrough and update |
