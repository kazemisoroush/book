# US-034 — Story Mood Registry

## Problem Statement

The pipeline has no representation of the *story's emotional arc* — the reader's
felt register over a span of narrative. The existing `scene` field captures
physical setting (drawing room, cave, battlefield), which is the wrong axis:
a chase sequence can span four scenes on one emotional arc, and a single
drawing room can hold three moods across twenty pages.

US-012 (music) and US-035 (narrator emotion) both need this signal. Without a
shared representation each will reinvent it and the two will drift.

## Proposed Solution

Introduce `Mood` (entity) + `MoodRegistry`, mirroring the existing
`Scene` / `SceneRegistry` pattern (`src/domain/models.py:302-341`) — but with
explicit span fields, because a mood is an entity with a lifetime, not a
reusable value object.

Free-form description (no whitelist). Downstream consumers are AI systems
that read natural language directly.

**Shape.**

- `Mood` carries `mood_id`, free-form `description`, `start` / `end`
  section refs, and optional `continues_from: mood_id` for cross-chapter arcs.
- A mood is bounded within a single chapter (`start.chapter == end.chapter`).
  Arcs that bridge chapters (e.g. Ch 46–47 Lydia crisis) open a fresh mood at
  the new chapter with `continues_from` set.
- `MoodRegistry` is a `dict[mood_id, Mood]` on `Book`, threaded through
  parsing alongside `SceneRegistry`.
- Each `Section` gains `mood_id: Optional[str]`, populated post-parse from the
  registry so consumers get O(1) lookup. Registry remains authoritative.

**LLM contract.** Per-chunk output emits one of:

- `{"mood": "open", "description": "..."}` — opens a new mood at this section
- `{"mood": "continue", "mood_id": "..."}` — current chunk belongs to an
  already-open mood
- `{"mood": "close_and_open", "close_mood_id": "...", "description": "..."}`
  — shifts arc at this section

Unknown `mood_id` references are coerced to `open` with a structlog warning.

**Post-parse pipeline.**

1. **Close pass.** Any mood still open at end-of-chapter is closed at the
   last section; if the first chunk of the next chapter opens with similar
   semantics the parser may set `continues_from` on the new mood (LLM-driven,
   not embedding-based).
2. **Merge pass.** Any mood shorter than 2 sections is merged into whichever
   neighbour is textually closer. Prevents per-paragraph mood churn.
3. **Back-fill pass.** `Section.mood_id` is populated from the registry.

**No feature flag.** Per TD-027 the prompt is static; the LLM always emits
mood signals. Feature flags for *consumers* live in US-012 and US-035.

## Examples

### Book JSON fragment (Pride and Prejudice)

```json
"mood_registry": {
  "ch1_dry_opening_commentary": {
    "mood_id": "ch1_dry_opening_commentary",
    "description": "dry, wry social commentary; a knowing narrator setting the tone with gentle irony",
    "start": {"chapter": 1, "section": 3},
    "end":   {"chapter": 1, "section": 4},
    "continues_from": null
  },
  "ch1_bennet_domestic_banter": {
    "mood_id": "ch1_bennet_domestic_banter",
    "description": "comic domestic banter, brittle nerves colliding with sardonic detachment; nothing truly at stake",
    "start": {"chapter": 1, "section": 5},
    "end":   {"chapter": 1, "section": 38},
    "continues_from": null
  },
  "ch34_hunsford_confrontation": {
    "mood_id": "ch34_hunsford_confrontation",
    "description": "raw confrontation between pride and contempt, the air electric with mutual insult",
    "start": {"chapter": 34, "section": 1},
    "end":   {"chapter": 34, "section": 22},
    "continues_from": null
  },
  "ch46_lydia_crisis": {
    "mood_id": "ch46_lydia_crisis",
    "description": "cold panic rising under polite surfaces; a family disaster arriving in a single letter",
    "start": {"chapter": 46, "section": 4},
    "end":   {"chapter": 46, "section": 41},
    "continues_from": null
  },
  "ch47_lydia_crisis_continued": {
    "mood_id": "ch47_lydia_crisis_continued",
    "description": "dread settling into numb worry, the long pull of waiting for news",
    "start": {"chapter": 47, "section": 1},
    "end":   {"chapter": 47, "section": 52},
    "continues_from": "ch46_lydia_crisis"
  }
}
```

### Section reference (indexing field, post-parse)

```json
{
  "text": "IT is a truth universally acknowledged, that a single man in possession of a good fortune must be in want of a wife.",
  "beats": [ ... ],
  "section_type": null,
  "mood_id": "ch1_dry_opening_commentary"
}
```

### LLM per-chunk emission (prompt output)

```json
// first chunk of Ch 1 main text
{"mood": "open", "description": "dry, wry social commentary; a knowing narrator..."}

// middle chunk of the Bennet banter
{"mood": "continue", "mood_id": "ch1_bennet_domestic_banter"}

// chunk where Mrs Bennet's nagging shifts into Mr Bennet's resigned sarcasm
{"mood": "close_and_open",
 "close_mood_id": "ch1_bennet_domestic_banter",
 "description": "resigned paternal sarcasm; a weary man enjoying his own wit"}
```

### Domain model sketch

```python
@dataclass(frozen=True)
class SectionRef:
    chapter: int
    section: int

@dataclass
class Mood:
    mood_id: str
    description: str
    start: SectionRef
    end: SectionRef
    continues_from: Optional[str] = None

@dataclass
class MoodRegistry:
    _moods: dict[str, Mood] = field(default_factory=dict)
    # upsert / get / all / to_dict / from_dict mirroring SceneRegistry
```

## Dependencies

- None. Prerequisite for US-012 and US-035.

## Out of Scope

- Consuming moods in music (→ US-012) or narrator voice (→ US-035).
- Closed vocabulary for `description`. Free-form by design.
- Learning moods from audio feedback.
