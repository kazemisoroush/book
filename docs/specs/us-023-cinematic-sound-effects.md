# US-023 — Cinematic Sound Effects

## Goal

Enhance audiobook immersion by inserting **diegetic sound effects** (explicit narrative events like door knocks, coughs, thunder) into inter-segment silence gaps, creating the intimate feel of a radio drama. Ambient sound provides persistent environmental backdrop; speech and SFX are the foreground.

---

## Problem

Pride and Prejudice is purely dialogue and narration with silence between segments. Moments like "she coughed" or "a knock at the door" are described but not **heard**. Adding brief, evidence-based sound effects makes these moments vivid without fabrication or overuse.

---

## Concept

**Audio hierarchy:**
1. **Speech** (dialogue + narration) — foreground, primary focus
2. **Sound effects** — foreground, discrete events in silence gaps (0.5–1.5 seconds each)
3. **Ambient** — background, continuous, always present but recessive (-28 dB)

**Example (Pride & Prejudice, Chapter 1):**
```
[narration: "It was a truth universally acknowledged..."]
[silence]
[dialogue: "My dear Mr. Bennet, have you heard..."]
[silence + SFX: door knock]
[narration: "A visitor had arrived."]
[ambient: quiet drawing room, -28 dB throughout]
```

---

## Acceptance criteria

1. `Segment` model gains `sound_effect_description: Optional[str] = None` — a natural-language description of the sound effect (e.g., "dry cough", "firm knock on wooden door")

2. AI parser provides `sound_effect_description` **only if the text explicitly names the action**:
   - Text: "she coughed loudly" → SFX: "dry cough"
   - Text: "a knock at the door" → SFX: "firm knock on wooden door"
   - Text: "thunder crashed" → SFX: "thunder crash"
   - NO invention, NO inference, NO hallucination

3. New `src/tts/sound_effects_generator.py` module:
   ```python
   def get_sound_effect(
       description: str,
       output_dir: Path,
       client: ElevenLabs,
       duration_seconds: float = 2.0,
   ) -> Optional[Path]:
       """Return path to sound effect MP3.

       Generates via ElevenLabs Sound Effects API on first call;
       caches by description hash in output_dir/sfx/{hash}.mp3.
       Returns None on API failure (logged as warning, not error).
       """
   ```

4. `TTSOrchestrator` wires sound effects into silence gaps:
   - After stitching speech audio, for each segment with `sound_effect_description`:
     - Call `get_sound_effect()` to obtain audio
     - Insert SFX at **START** of inter-segment silence
     - Silence becomes: [SFX] + [original silence]
     - Total gap length increases by SFX duration
   - Ambient runs throughout at -28 dB (no ducking, static level)

5. Feature flag `cinematic_sfx_enabled: bool = True` on TTSOrchestrator constructor (allow disable)

6. When `sound_effect_description` is None or SFX API fails, behavior is identical to today (no regression)

7. New unit tests cover:
   - `Segment` round-trips `sound_effect_description` through serialization
   - SFX generator caching and API failure handling
   - Orchestrator inserts SFX at correct gap positions
   - Feature flag disable skips SFX entirely

8. All existing tests continue to pass

---

## Out of scope

- Ambient volume ducking during SFX (ambient stays static)
- Per-chapter SFX frequency limits
- User-configurable SFX filtering or thresholds
- SFX during dialogue/narration (silence gaps only)
- AI confidence scoring (all explicit mentions are marked)

---

## Key design decisions

### Evidence-based detection only
The AI must not invent sounds. Only explicit textual mentions trigger SFX. This keeps the experience grounded and trustworthy — readers feel the SFX are "real" to the narrative.

### SFX expands silence, doesn't replace it
Original silence remains; SFX is prepended. Total gap grows. This maintains naturalness — the pause isn't shortened, just enriched. Prevents the audio from feeling "rushed."

### Ambient is always there
Unlike SFX (which are conditional on narrative events), ambient runs the entire chapter at a constant, recessive level (-28 dB). It's the audiobook's "room tone." Speech and SFX pop against it; readers can tune it out mentally or enjoy it subconsciously.

### Caching by description hash
Same description → same file across chapters. Reduces API calls and creates consistency. "Door knock" in Chapter 1 and Chapter 3 sound identical.

### Graceful API failures
If ElevenLabs Sound Effects API is down, that moment loses its SFX but the chapter still produces. Logged as warning. Same pattern as US-011 ambient.

---

## Files changed (expected)

| File | Change |
|---|---|
| `src/domain/models.py` | Add `sound_effect_description: Optional[str] = None` to `Segment` |
| `src/parsers/ai_section_parser.py` | Extend prompt to request `sound_effect_description` for explicit actions; parse into segments |
| `src/tts/sound_effects_generator.py` | **New module** — generate and cache SFX via ElevenLabs Sound Effects API |
| `src/tts/tts_orchestrator.py` | Insert SFX into silence gaps; add `cinematic_sfx_enabled` flag |

---

## Relationship to other specs

- **US-011 (Ambient)**: Ambient provides recessive environmental backdrop
- **US-016 (Inter-Segment Silence)**: Silence gaps are where SFX are inserted
- **US-019 (TTS Context)**: No direct interaction; context resolution is per-segment, not audio-level
- **US-020 (Scenes)**: No direct interaction; scenes inform ambient, not SFX

---

## Implementation notes

- Follow SOLID principles: inject dependencies (SFX generator, provider, client)
- TDD: write tests for SFX insertion logic, caching, feature flag before implementation
- No mocks beyond the SFX generator call (at most 1 mock per test)
- Structured logging only (structlog)
- Type annotations on all public functions
