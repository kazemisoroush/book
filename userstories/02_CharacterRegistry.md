# User Story 02 — Character Registry

## Problem Statement

After AI workflow processing, some segments are narrated by `null`. Beyond fixing
that immediate bug, we need a proper model: every segment must be owned by a
character, and that character must be consistent across the entire book so a
single TTS voice can be assigned to it.

---

## Definition: What is a Character?

**A character is a voice, not a person.**

- Daniel Radcliffe narrating Harry Potter at age 14 and at age 30 are *two
  different characters* — same actor, different voices.
- The Narrator is a character. There is always at least one.
- A character maps 1-to-1 with a TTS voice slot. Once assigned, all segments
  owned by that character are rendered with the same voice.

This means the registry is about *voice consistency*, not literary character
identity.

---

## Core Problems

### 1. Maintain the registry while reading the book

As the AI processes sections (chapter by chapter, section by section), it must
build and update a shared `CharacterRegistry`. When it encounters a speaker it
has already seen, it reuses the existing entry. When it encounters a new one, it
adds a placeholder. The registry is **eventually consistent** — a character can
exist with no voice assigned yet.

The `CharacterRegistry` must be threaded through the parsing pipeline. The AI
section parser receives the current registry and returns both the segmented
section and any registry mutations (new or updated characters).

### 2. Segments hold a foreign key to the registry

`Segment.speaker` (currently a raw `Optional[str]`) becomes
`Segment.character_id: Optional[str]` — a stable reference into
`CharacterRegistry`. The human-readable name lives only in the registry.

Narration segments are no longer `speaker=None`. They are assigned to the
default Narrator character (`character_id = "narrator"`). This is what fixes
the `null` narrator bug.

### 3. Unknown characters resolve over time

The registry is built incrementally. A character created from the first mention
of "an old man" may later be resolved to "Dumbledore" as context accumulates.
That is fine — the model allows it. Both `Book` and `CharacterRegistry` reach
their final state only when the full book has been processed. Neither is
required to be final mid-flight.

---

## Data Model Sketch

```python
@dataclass
class Character:
    character_id: str          # stable slug or UUID; "narrator" is reserved
    name: str                  # display name, e.g. "Harry Potter (young)"
    description: Optional[str] # voice description used for TTS assignment
    is_narrator: bool = False

@dataclass
class CharacterRegistry:
    characters: list[Character] = field(default_factory=list)
    # always bootstrapped with a default Narrator entry

# Segment changes:
# speaker: Optional[str]  →  character_id: Optional[str]
```

`CharacterRegistry` ships alongside `Book` — they are sister outputs of the
pipeline, not nested inside each other.

---

## AI Contract

The AI section parser prompt is extended with:
- the current registry (list of `character_id` + `name` pairs) as context
- an instruction to reuse existing IDs for known characters and emit new entries
  for genuinely new ones

The parser returns a structured response that includes both the segment list and
a diff to apply to the registry (new characters, name corrections). The caller
applies the diff and passes the updated registry to the next section.

---

## Out of Scope (for this story)

- Multiple narrators (e.g., alternating POV chapters) — deferred
- Spoiler detection (characters revealing plot via their name) — deferred
- Voice assignment to characters (ElevenLabs TTS mapping) — next story
- Merging two registry entries that turn out to be the same character — deferred
