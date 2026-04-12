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
| `scene_id` | `str` | `"scene_cave"` |
| `environment` | `str` | `"cave"`, `"street"`, `"car_interior"`, `"battlefield"` |
| `acoustic_hints` | `list[str]` | `["echo", "confined", "quiet"]` |
| `voice_modifiers` | `dict[str, float]` | `{"stability_delta": -0.10, "style_delta": 0.0, "speed": 0.90}` |

### SceneRegistry

Scenes are managed through a **SceneRegistry**, analogous to
`CharacterRegistry` but for *places* instead of *people*. The registry
holds all detected scenes keyed by `scene_id` and is threaded through the
AI section parser pipeline alongside the character registry.

Each `Segment` carries an optional `scene_id` referencing a scene in the
registry. This enables per-segment scene assignment — different segments
within the same chapter can belong to different scenes (e.g., a character
moves from indoors to outdoors mid-chapter).

The `SceneRegistry` provides:
- `upsert(scene)` — add or replace a scene
- `get(scene_id)` — look up a scene by ID
- `all()` — list all registered scenes
- `to_dict()` / `from_dict()` — serialization round-trip

### Scene detection

Scenes are detected per-section by the AI parser during segmentation.
When the AI detects a scene, it is upserted into the registry and the
`scene_id` is stamped on all segments in that section. The AI prompt
includes existing scenes from the registry so it can reuse `scene_id`
values instead of creating duplicates.

---

## Acceptance criteria

1. A `Scene` domain model exists in `src/domain/models.py` with at least
   `scene_id`, `environment`, `acoustic_hints`, and `voice_modifiers` fields.
2. A `SceneRegistry` exists with `upsert`, `get`, `all`, `to_dict`, `from_dict`.
3. Each `Segment` has an optional `scene_id: str | None` referencing the registry.
4. `Book` has a `scene_registry: SceneRegistry` field.
5. The AI parser accepts a `SceneRegistry`, upserts detected scenes, and
   assigns `scene_id` to segments.
6. `SegmentContextResolver` looks up scenes from the registry via
   segment's `scene_id` and applies voice modifiers.
7. `AudioOrchestrator` passes `Book.scene_registry` to the resolver.
8. When `scene_id` is `None`, behaviour is identical to no scene (no regression).
9. Full serialization round-trip works (Book.to_dict -> from_dict preserves scenes).
10. All existing tests continue to pass.

---

## Voice-setting modifiers

Voice modifiers are **LLM-provided per scene**, not looked up from a static
table. The AI prompt includes example modifier values by environment type as
guidance, and the LLM returns contextually appropriate `voice_modifiers` as
part of the scene response:

```json
"voice_modifiers": {"stability_delta": -0.05, "style_delta": 0.0, "speed": 0.90}
```

Example guidance values provided in the prompt:

| Environment | stability delta | style delta | speed | Rationale |
|---|---|---|---|---|
| `outdoor_open` | 0.00 | +0.05 | 1.00 | Slight projection |
| `indoor_quiet` | +0.05 | -0.05 | 0.95 | Restrained, intimate |
| `cave` / `tunnel` | -0.05 | 0.00 | 0.90 | Slower, aware of echo |
| `car` / `vehicle` | +0.05 | 0.00 | 1.00 | Confined, conversational |
| `battlefield` | -0.10 | +0.15 | 1.10 | Shouting, urgent |
| `whisper_scene` | +0.10 | -0.10 | 0.85 | Hushed, controlled |

The `SegmentContextResolver` reads `scene.voice_modifiers` directly and
applies additive deltas with clamping. When `voice_modifiers` is empty or
the scene is `None`, voice settings pass through unchanged.

---

## Design notes

- Scene detection reuses the same AI call that segments sections. The
  prompt receives the full section text and asks for the physical setting
  alongside voice modifiers.
- `SceneRegistry` follows the same patterns as `CharacterRegistry`
  (upsert, get, to_dict/from_dict).
- Scene is a value object (frozen dataclass), not an entity with
  identity lifecycle. The registry holds them by `scene_id`.
- Scenes are per-segment via `scene_id`, not per-chapter. Different
  segments can reference different scenes within the same chapter.
- The modifier system is additive (deltas on top of the
  emotion-based preset), not a replacement. A character who is `angry` in
  a `cave` gets the angry preset adjusted by the scene's voice modifiers.
- The AI prompt includes existing scenes from the registry so the AI can
  reuse `scene_id` values instead of creating duplicates.
- `Chapter.scene` has been removed; scenes are tracked exclusively via
  `SceneRegistry` on `Book` and `scene_id` on each `Segment`.
- This follows the same pattern as US-019 Fix 3: the LLM provides
  contextually appropriate values instead of mapping through a static table.

---

## Out of scope

- Post-processing audio effects (reverb, EQ) — valuable but separate work.
- Scene-aware background audio (overlaps with US-011 ambient sound).
- Visual scene descriptions for non-audio outputs.
