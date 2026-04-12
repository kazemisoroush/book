# TD-011 — Reuse ElevenLabs Designed Voices

## Goal

Stop recreating ElevenLabs voices on every synthesis run. Look up existing
voices by a deterministic key before calling the Voice Design API, and reuse
them when they already exist. This eliminates redundant API calls, avoids
polluting the ElevenLabs account with duplicate voices, and makes re-runs
faster and cheaper.

---

## Problem

`VoiceAssigner.assign()` calls `design_voice()` for every character with a
`voice_design_prompt` on every run. `design_voice()` always creates a brand
new voice via the two-step ElevenLabs flow (create-previews → create-voice).
This means:

1. **Duplicate voices accumulate** in the ElevenLabs account — re-running
   the same book creates N new voices each time.
2. **Wasted API calls** — the Voice Design API is slow (~3-5 s per character)
   and costs credits.
3. **Voice inconsistency** — the same character gets a different voice on
   every run, so partial re-synthesis produces mismatched audio.

The ElevenLabs voice library is persistent — voices survive across sessions.
We should treat it as a cache and only create what doesn't already exist.

---

## Concept

### Deterministic voice key

Each designed voice needs a stable, unique identifier we control. The key
must be deterministic so we can look it up on subsequent runs:

```
{book_title}::{book_author}::{character_id}
```

For example: `Pride and Prejudice::Jane Austen::mr_bennet`

This key is stored as the `voice_name` in ElevenLabs when creating the
voice, and looked up via the `GET /v2/voices?search=` endpoint on
subsequent runs.

**Why this key?**
- `character_id` alone is not unique across books (e.g. "narrator" exists
  in every book).
- Book title + author scopes the voice to a specific production.
- `character_id` (not `name`) avoids collisions when two characters share
  a display name but have different registry IDs.

### Lookup-before-create flow

Replace the current "always create" logic with:

1. **Search** — `GET /v2/voices?search={key}` to find voices whose name
   matches the deterministic key.
2. **Match** — if a voice with an exact `name == key` exists, return its
   `voice_id` immediately (cache hit).
3. **Create** — if no match, run the existing two-step design flow and
   use the deterministic key as `voice_name`.

### Where the logic lives

**New module: `src/audio/voice_registry.py`**

A single-purpose adapter that owns the lookup-before-create boundary.
It encapsulates the ElevenLabs voice library interaction behind a clean
interface:

```python
class ElevenLabsVoiceRegistry:
    """Manages voice lifecycle in the ElevenLabs account.

    Lookup-before-create: searches for an existing voice by deterministic
    key, returns its voice_id on hit, or delegates to voice_designer to
    create a new one on miss.
    """

    def get_or_create_voice(
        self,
        book_title: str,
        book_author: str,
        character_id: str,
        voice_description: str,
        character_name: str,
    ) -> str:
        """Return a voice_id, creating one only if it doesn't exist."""
        ...
```

**Call site: `src/audio/voice_assigner.py`**

`VoiceAssigner` receives an `ElevenLabsVoiceRegistry` instead of a raw
ElevenLabs client. The assigner delegates voice resolution to the registry
and no longer calls `design_voice()` directly:

```python
# Before (current):
designed_id = design_voice(
    description=char.voice_design_prompt,
    character_name=char.name,
    client=self._elevenlabs_client,
)

# After:
designed_id = self._voice_registry.get_or_create_voice(
    book_title=self._book_title,
    book_author=self._book_author,
    character_id=char.character_id,
    voice_description=char.voice_design_prompt,
    character_name=char.name,
)
```

**`voice_designer.py` stays unchanged** — it remains a pure "create voice"
function. `ElevenLabsVoiceRegistry` calls it when the lookup misses.

### Why not put the lookup in `voice_designer.py`?

Single Responsibility. `voice_designer.py` knows how to create a voice.
`voice_registry.py` knows how to manage the voice lifecycle (lookup +
create + key derivation). Mixing lookup logic into the designer would
give it two reasons to change.

### Why not put the lookup in `voice_assigner.py`?

`VoiceAssigner` is an assignment algorithm — it decides which character
gets which voice. It should not know about the ElevenLabs voice library
API. Pushing the lookup there would leak the ElevenLabs boundary into the
assignment layer.

---

## Acceptance criteria

1. Re-running synthesis for the same book reuses previously designed
   voices — no new voices are created in ElevenLabs.
2. Voices are looked up by a deterministic key
   (`{title}::{author}::{character_id}`).
3. When no matching voice exists, a new one is created with the key as
   its `voice_name`.
4. `VoiceAssigner` does not call `design_voice()` directly — it delegates
   to `ElevenLabsVoiceRegistry`.
5. `voice_designer.py` is unchanged (still a pure create function).
6. `ElevenLabsVoiceRegistry` is the only module that calls the ElevenLabs
   voice listing API.
7. The search uses `GET /v2/voices?search={key}` and validates an exact
   `name` match (search is fuzzy, so partial matches must be filtered).
8. All existing tests continue to pass.
9. Unit tests for `ElevenLabsVoiceRegistry` cover: cache hit, cache miss,
   API error fallback, key derivation.

---

## Out of scope

- Deleting stale voices from ElevenLabs (future cleanup task).
- Migrating existing voices to the new naming scheme.
- Voice versioning (re-creating a voice when its description changes) —
  a future spec if needed.
- Narrator voice design (narrator uses the first voice in the pool, not
  the design API).
- Changing the demographic matching fallback — only the design path is
  affected.
