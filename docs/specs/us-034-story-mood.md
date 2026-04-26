# US-034 — Story Mood Detection

## Problem

The pipeline has no representation of the *story's emotional arc* — the
reader's felt emotional register as the narrative unfolds. Several downstream
features need this signal but have nowhere to read it from:

- **US-012 (Background Music)** wants to choose music that matches the story's
  emotional beat, not the physical scene.
- **US-035 (Narrator Emotion)** wants to modulate the narrator's vocal
  register with the story's mood, not with per-sentence emotion.

The existing `scene` field captures *physical setting* (drawing room, cave,
battlefield). That is the wrong axis for emotion:

- A single chase sequence can cut across alley → rooftop → car → warehouse
  (four scenes) but hold **one** mood throughout.
- A single drawing room can hold several moods across 20 pages.

Without a shared mood signal, music and narrator voice will drift: music may
play "triumphant" while the narrator reads in "mournful" tone.

## Proposed Solution

Introduce `StoryMood` as a first-class domain concept emitted by the AI
parser alongside existing segment data. The signal is **free-form** — the
LLM writes a natural-language description; downstream AI consumers
(music generation, voice design) interpret it directly.

**Domain model.** Add a `StoryMood` dataclass with a single field:

- `description: str` — a free-form natural-language phrase describing the
  reader's emotional register at this point in the narrative. Examples the
  LLM might produce:
  - `"a frantic chase through wet streets at night, pulse-pounding dread"`
  - `"quiet grief at a graveside, the finality of loss settling in"`
  - `"breathless wonder at a sight no one has seen before"`
  - `"warm, comfortable domestic banter, nothing at stake"`
  - `"neutral exposition, no strong emotional charge"`

No enum, no whitelist, no coerced labels. The same LLM that produces the
mood also ultimately drives the consumers that read it (music prompt
generation, narrator voice design), so a closed vocabulary would add
translation layers without value.

**Detection.** The section-parser prompt is extended to emit a top-level
`story_mood` key on each chunk's output, containing `description`. The field
is not gated by a feature flag (per TD-027: prompts are static). Downstream
consumers decide whether to use the signal.

**Persistence.** StoryMood is attached at the chunk level in the domain
model and surfaces on the chunk in `output.json`. No smoothing or block
logic — each chunk carries its own description; consumers handle transitions
however they see fit (a music provider may diff adjacent descriptions to
decide whether to regenerate; a narrator voice step may treat each chunk
independently).

**Feature-flag discipline.** No feature flags introduced by this spec.
StoryMood detection is unconditional; the prompt always requests it.
Downstream consumer specs (US-012, US-035) introduce their own deterministic
feature flags gated by the `FeatureFlags` class per TD-027.

## Acceptance Criteria

1. `src/domain/models.py` defines a `StoryMood` dataclass with a single
   field: `description: str`. No validation against a whitelist.
2. The chunk-level domain model returned by the parser carries a
   `story_mood: StoryMood` field.
3. `src/parsers/prompts/section_parser.prompt` unconditionally instructs the
   LLM to emit `story_mood.description` at the top level of its JSON output,
   as a free-form natural-language phrase describing the reader's emotional
   register. The prompt includes 2–3 example phrases to anchor tone (not a
   whitelist).
4. The JSON example rendered by `PromptBuilder` includes the `story_mood`
   field.
5. `src/parsers/prompt_builder.py` does not gate the story-mood instructions
   behind any Jinja `{% if %}` conditional. Prompt is static.
6. Empty or missing `story_mood.description` is tolerated — the field is
   coerced to an empty `StoryMood("")` with a `story_mood_missing` structlog
   warning; does not raise.
7. `output.json` surfaces `story_mood.description` on each chunk.
8. `make verify` passes end-to-end; generated `output.json` contains
   non-empty `story_mood.description` on chunks with discernible mood.
9. `ruff check src/` and `mypy src/` pass.

## Out of Scope

- Consuming `story_mood` in music generation (→ US-012).
- Consuming `story_mood` in narrator voice modulation (→ US-035).
- Any closed vocabulary or label whitelist.
- Mood smoothing, block-collapsing, or cross-chunk continuity logic. Each
  chunk stands alone; consumers decide how to handle runs.
- Persisting mood history across books.
- Adding new `BeatType` values. StoryMood is a property *of* the chunk,
  not a new beat type.

## Dependencies

- None. This spec is the prerequisite for US-012 and US-035.

## Key Design Decisions

### Why free-form instead of a closed vocabulary?

The signal's producer (the LLM) and its consumers (music-generation prompts,
voice-design prompts) are all AI systems that natively consume natural
language. A closed label set would force two translation layers — LLM →
label → consumer — where the label is strictly less expressive than the
LLM's original description. Free-form preserves nuance ("quiet grief at a
graveside" carries information that a `grief` label erases).

### Why no smoothing / mood blocks?

Block computation requires a notion of "same mood as previous", which only
makes sense with a closed vocabulary. With free-form descriptions, the
producer already writes a fresh phrase per chunk; any grouping logic is a
downstream consumer's concern.

### Why no feature flag?

Per TD-027, prompt content is not a flag. The LLM always emits
`story_mood`; if unused, it is inert. Feature flags for *consumers* of this
signal live in US-012 and US-035.
