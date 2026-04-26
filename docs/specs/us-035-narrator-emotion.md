# US-035 — Narrator Emotion

## Problem Statement

The narrator voice is currently forced to emotional neutrality. The
section-parser prompt instructs *"Use 'neutral' for narration..."*, and
narrator beats are pinned at `stability=0.65`, `style=0.05`, `speed=1.0`
regardless of context. A flat narrator is the single largest gap versus
professional audiobook narration (Jim Dale / Stephen Fry on *Harry Potter*),
where the narrator carries genuine sorrow at a funeral and genuine tension
during a chase — in a narrower band than characters, but not zero.

## Proposed Solution

Narrator voice settings are derived from the current `Mood` (US-034), computed
once per mood and cached on the `Mood` entity, then applied to every narrator
beat falling in that mood's span.

**Mood gains a `narrator_voice` field.** Populated by a lightweight AI call
that reads the free-form `Mood.description` and returns four values:

- `stability` — clamped to `[0.45, 0.70]`
- `style` — clamped to `[0.00, 0.25]`
- `speed` — clamped to `[0.90, 1.05]`
- `prompt` — free-form natural-language direction for the TTS provider
  (consumed the same way character `emotion` is today)

Clamping is deterministic post-processing; the AI is given the band in its
instructions but the clamp is enforced in code regardless.

**One call per Mood, not per beat.** A book with ~60 moods → 60 calls,
amortised across hundreds of narrator beats.

**Narrator beat resolution.** At synthesis time, the beat resolver looks up
`Section.mood_id` → `MoodRegistry.get(...)` → `Mood.narrator_voice`, and
copies `stability` / `style` / `speed` / `prompt` onto the beat. Character
beats are untouched.

**Flag-gated.** `FeatureFlags.narrator_emotion_enabled` (default `False`,
hardcoded per TD-027). When off, `Mood.narrator_voice` is not computed and
narrator beats use the current flat defaults. `Section.mood_id` is still
populated by US-034 either way.

**Why free-form, not a table.** Previous draft hardcoded a
`mood_label → settings` table keyed on a closed vocabulary. US-034 is
free-form, so that approach doesn't apply — the AI that writes the mood
description is the right system to read it and produce voice settings.
The clamp is the only deterministic guardrail needed.

## Examples

### Mood entity with narrator voice populated

```json
"ch34_hunsford_confrontation": {
  "mood_id": "ch34_hunsford_confrontation",
  "description": "raw confrontation between pride and contempt, the air electric with mutual insult",
  "start": {"chapter": 34, "section": 1},
  "end":   {"chapter": 34, "section": 22},
  "continues_from": null,
  "narrator_voice": {
    "stability": 0.48,
    "style": 0.22,
    "speed": 1.02,
    "prompt": "tight, clipped narration; controlled anger beneath the surface; consonants hard"
  }
}
```

### Narrator beats across different moods (Pride and Prejudice)

Same narrator, settings shift with mood.

**Ch 1 — `ch1_bennet_domestic_banter` (comic register):**

```json
{
  "text": "said his lady to him one day",
  "beat_type": "narration",
  "character_id": "narrator",
  "voice_stability": 0.55,
  "voice_style": 0.18,
  "voice_speed": 1.00,
  "mood_id": "ch1_bennet_domestic_banter"
}
```

**Ch 35 — `ch35_darcy_letter_reckoning` (quiet recalibration):**

```json
{
  "text": "She grew absolutely ashamed of herself.",
  "beat_type": "narration",
  "character_id": "narrator",
  "voice_stability": 0.58,
  "voice_style": 0.18,
  "voice_speed": 0.93,
  "mood_id": "ch35_darcy_letter_reckoning"
}
```

**Ch 46 — `ch46_lydia_crisis` (cold panic):**

```json
{
  "text": "Elizabeth could hardly help smiling, at so convenient a proposal...",
  "beat_type": "narration",
  "character_id": "narrator",
  "voice_stability": 0.47,
  "voice_style": 0.23,
  "voice_speed": 1.03,
  "mood_id": "ch46_lydia_crisis"
}
```

**Ch 61 — `ch61_closing_resolution` (warm epilogue):**

```json
{
  "text": "Happy for all her maternal feelings was the day on which Mrs. Bennet got rid of her two most deserving daughters.",
  "beat_type": "narration",
  "character_id": "narrator",
  "voice_stability": 0.62,
  "voice_style": 0.14,
  "voice_speed": 0.96,
  "mood_id": "ch61_closing_resolution"
}
```

Today every one of these would be `0.65 / 0.05 / 1.00`.

### Flag off — narrator defaults preserved

```json
{
  "text": "She grew absolutely ashamed of herself.",
  "beat_type": "narration",
  "voice_stability": 0.65,
  "voice_style": 0.05,
  "voice_speed": 1.00,
  "mood_id": "ch35_darcy_letter_reckoning"
}
```

`mood_id` is still populated (US-034 runs regardless); voice settings fall
back to the flat defaults.

### Domain model sketch

```python
@dataclass(frozen=True)
class NarratorVoice:
    stability: float  # clamped to [0.45, 0.70]
    style: float      # clamped to [0.00, 0.25]
    speed: float      # clamped to [0.90, 1.05]
    prompt: str

@dataclass
class Mood:
    mood_id: str
    description: str
    start: SectionRef
    end: SectionRef
    continues_from: Optional[str] = None
    narrator_voice: Optional[NarratorVoice] = None  # populated by US-035
```

## Dependencies

- **US-034 — Story Mood Registry** (hard prerequisite).
- **TD-027 — Simplify Feature Flags** (soft prerequisite for the flag shape).

## Out of Scope

- Mood detection (→ US-034).
- Music generation (→ US-012).
- Per-beat narrator emotion — narrator modulation is per-mood, not per-sentence.
- Multiple narrator voices / personas.
