# TD-006 — Ping-Pong Speaker Attribution Edge Case

**Priority**: Low
**Effort**: Unknown
**Status**: Open

## Problem

A single dialogue line in Chapter 1 of Pride and Prejudice is persistently
misattributed despite multiple mitigation attempts:

> "Is he married or single?"

This line should be spoken by `mr_bennet` (turn-taking: Mrs. Bennet just said
"Bingley.", so Mr. Bennet speaks next). The model consistently attributes it
to `mrs_bennet` because the line is semantically consistent with her
character voice (eager curiosity about eligible bachelors).

## What was tried

| Attempt | Result |
|---|---|
| Context window = 3 | Wrong |
| Context window = 5 | Wrong (but fixed the preceding line "What is his name?") |
| Context window = 10 | Worse — more Mrs. Bennet context reinforces her voice profile |
| Full chapter context (1000) | Worse — same reason |
| Ping-pong prompt rule added | Fixed "What is his name?"; "Is he married or single?" still wrong |
| Claude 3 Opus (EOL) | Not tested |
| Claude Opus 4.6 | Wrong — same misattribution |

## Root cause

The model's semantic confidence ("this sounds like Mrs. Bennet") overrides the
structural turn-taking signal even when that signal is explicit in the context.
More context makes it worse by building a stronger character voice profile for
Mrs. Bennet.

## Possible approaches

1. **Stronger ping-pong enforcement in prompt** — make the alternation rule
   more explicit, e.g. "If the previous dialogue line was `[X]`, the next
   line MUST be attributed to a different speaker unless narration explicitly
   names `[X]` as the speaker."
2. **Post-processing pass** — after AI segmentation, detect runs of 3+
   consecutive same-speaker dialogue lines and flag/correct them using
   turn-taking heuristics.
3. **Section-level speaker hint** — pass the expected next speaker as a
   hint derived from the previous section's last resolved speaker.

## Files affected

`src/parsers/ai_section_parser.py` — `_build_prompt()` rules section
