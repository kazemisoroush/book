# US-003: Include Character Registry in Book JSON Output

## Goal

`Book.to_dict()` currently excludes `character_registry`. Downstream consumers
(TTS pipeline, debugging, re-runs) need the character data — including `sex` and
`age` — in the serialised output.

## Acceptance Criteria

1. `Book.to_dict()` includes a `character_registry` key containing the list of
   serialised `Character` objects (using `Character.to_dict()` for each).
2. `Book.from_dict()` (if it exists or is added) round-trips the registry.
3. Existing tests that assert `character_registry` is absent are updated to
   assert it is present with the correct shape.
4. All other tests pass. `ruff` and `mypy` clean.

## Out of Scope

- Changing the `Character` serialisation format (already defined in US-001)
- Any downstream consumer of the JSON (that is US-002)
