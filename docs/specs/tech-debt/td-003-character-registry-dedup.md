# TD-003 — Character Registry Deduplication

**Priority**: Medium
**Effort**: High
**Status**: Open

## Problem

The AI may create separate registry entries for the same character
across sections: `"harry"`, `"harry_potter"`, `"mr_potter"` all end up
as distinct voice slots. There is no deduplication or merging step.

## Impact

- Multiple TTS voice slots wasted on the same character
- Inconsistent character attribution in `output.json`
- ElevenLabs API cost inflated by redundant voice assignments

## What needs doing

- Add a post-parse deduplication pass that fuzzy-matches character names
  (edit distance, substring, alias detection)
- Either merge automatically with a confidence threshold or surface
  candidates for human confirmation
- Retroactively update all `Segment.character_id` references after a
  merge
- Consider a canonical name resolver in `CharacterRegistry`

## Constraints

- Must not break the `character_id` foreign key contract between
  `Segment` and `CharacterRegistry`
- Automatic merging should be conservative (high-confidence only);
  uncertain matches should surface as warnings, not silent merges

## Files affected

`src/domain/models.py` (`CharacterRegistry`), new
`src/domain/character_deduplicator.py`, `src/parsers/ai_section_parser.py`
