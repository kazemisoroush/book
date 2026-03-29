# TD-004 — Multi-POV / Multiple Narrators

**Priority**: Low
**Effort**: High
**Status**: Open

## Problem

All narration uses the single reserved `"narrator"` character regardless
of the book's point-of-view structure. Books with alternating POV
chapters (e.g. chapters narrated by different characters in first
person) sound wrong — every narrator uses the same voice.

## Impact

- Multi-POV novels (common in modern fiction) are mis-voiced
- No way to distinguish "Chapter told by Jane" from "Chapter told by
  Rochester"

## What needs doing

- Detect per-chapter narrator from AI context (first-person pronoun
  patterns, chapter headers, explicit attribution)
- Support multiple narrator slots in `CharacterRegistry` instead of the
  single reserved `"narrator"` ID
- Wire narrator detection into `AISectionParser` or a new pre-pass
- Update `VoiceAssigner` to assign distinct voices to narrator slots

## Constraints

- Must be backward-compatible: books with a single narrator continue
  to work with no config change
- Detection should be opt-in or automatic with high confidence only;
  wrong narrator assignment is worse than no detection

## Files affected

`src/domain/models.py` (`CharacterRegistry`), `src/parsers/ai_section_parser.py`,
`src/tts/voice_assigner.py`, possibly a new `src/parsers/narrator_detector.py`
