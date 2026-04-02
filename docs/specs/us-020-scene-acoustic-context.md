# US-020 — Scene / Acoustic Context

## Problem

Every segment in a chapter is synthesised with the same voice settings
regardless of the narrative environment. A character whispering in a cave
sounds identical to that character shouting across a battlefield. The TTS
layer has no concept of *where* the action takes place — only *who* is
speaking and *what emotion* they feel.

Real audiobook narrators instinctively adjust delivery based on setting:
hushed tones in a library, projection outdoors, intimate closeness in a
small room, echo-awareness in a cathedral. Our pipeline has no mechanism
to capture or apply this.

---

## Goal

Introduce a **Scene** entity that captures the acoustic environment of a
narrative segment. Scenes inform TTS voice settings (stability, style,
speed) and potentially post-processing effects so that character delivery
adapts to where the story is happening — not just what emotion is tagged.

---

## Concept

A **Scene** describes the acoustic context of a stretch of narrative:

| Field | Type | Example |
|---|---|---|
| `scene_id` | `str` | `"ch3_cave"` |
| `environment` | `str` | `"cave"`, `"street"`, `"car_interior"`, `"battlefield"` |
| `acoustic_hints` | `list[str]` | `["echo", "confined", "quiet"]` |
| `voice_modifiers` | `dict` | `{"stability_delta": -0.10, "speed": 0.90}` |

Scenes are analogous to `CharacterRegistry` but for *places* instead of
*people*. Just as the character registry tells us *who* is speaking, the
scene tells us *where* they are speaking.

### Scope boundaries

For the initial implementation, **chapter = scene**. Every segment in a
chapter shares the same scene. This is a simplification — real novels
change setting mid-chapter — but it avoids the need for AI scene-boundary
detection and still provides value.

Future iterations can introduce mid-chapter scene changes detected by the
AI parser, similar to how section boundaries are detected today.

---

## Acceptance criteria

1. A `Scene` domain model exists in `src/domain/models.py` with at least
   `scene_id`, `environment`, and `acoustic_hints` fields.
2. Each `Chapter` has an optional `scene: Scene | None` field.
3. The AI parser populates `scene` for each chapter (environment +
   acoustic hints derived from the text).
4. `TTSOrchestrator` reads the chapter's scene and adjusts voice settings
   accordingly (e.g. lower stability in echo-y environments, slower speed
   in intimate settings).
5. When `scene` is `None`, behaviour is identical to today (no regression).
6. All existing tests continue to pass.

---

## Potential voice-setting modifiers by environment

| Environment | stability delta | style delta | speed | Rationale |
|---|---|---|---|---|
| `outdoor_open` | 0.00 | +0.05 | 1.00 | Slight projection |
| `indoor_quiet` | +0.05 | -0.05 | 0.95 | Restrained, intimate |
| `cave` / `tunnel` | -0.05 | 0.00 | 0.90 | Slower, aware of echo |
| `car` / `vehicle` | +0.05 | 0.00 | 1.00 | Confined, conversational |
| `battlefield` | -0.10 | +0.15 | 1.10 | Shouting, urgent |
| `whisper_scene` | +0.10 | -0.10 | 0.85 | Hushed, controlled |

These are starting points — actual values need tuning against real output.

---

## Design notes

- Scene detection can reuse the same AI call that segments sections. The
  prompt already receives the full section text; adding "what is the
  physical setting?" is a minor prompt extension.
- Scene should be a value object (frozen dataclass), not an entity with
  identity lifecycle. Two chapters in the same cave share equivalent
  `Scene` instances but are not the "same" scene.
- The modifier system should be additive (deltas on top of the
  emotion-based preset), not a replacement. A character who is `angry` in
  a `cave` gets the angry preset adjusted by the cave modifiers.

---

## Out of scope

- Mid-chapter scene changes (requires scene-boundary detection).
- Post-processing audio effects (reverb, EQ) — valuable but separate work.
- Scene-aware background audio (overlaps with US-011 ambient sound).
- Visual scene descriptions for non-audio outputs.
