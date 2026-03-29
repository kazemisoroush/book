# TD-006 — Loudness Normalisation

**Priority**: Medium
**Effort**: Low
**Status**: Open

## Problem

Chapter audio files are not loudness-normalised. Chapters synthesised
from louder speech (many characters talking) vs quieter passages (long
narrator stretches) have noticeably different perceived volume. The
problem compounds when ambient or music layers are mixed in — a chapter
with no ambient can sound much louder than one with `-18 dB` ambient.

## Impact

- Listener experience degrades: volume jumping between chapters forces
  manual adjustment
- Music and ambient mixing levels are tuned relative to speech, but if
  speech itself varies, the calibrated ratios break
- Deliverable does not meet standard audiobook production specs
  (ACX / Audible require integrated loudness of −18 to −20 LUFS)

## What needs doing

Apply ffmpeg's `loudnorm` filter as the final post-processing step in
`TTSOrchestrator.synthesize_chapter()`, after ambient and music mixing:

```
ffmpeg -i chapter_raw.mp3 -af loudnorm=I=-18:TP=-1.5:LRA=11 chapter_NN.mp3
```

- Target integrated loudness: **−18 LUFS** (ACX-compatible)
- True peak ceiling: **−1.5 dBTP** (prevents clipping in lossy re-encode)
- Loudness range: **11 LU** (allows dynamic variation without over-compression)

Two-pass loudnorm (measure then apply) is more accurate but doubles
processing time. Single-pass is acceptable for this use case.

## Constraints

- Must run after ambient and music are already mixed, so the final
  normalised file reflects the composite loudness
- Normalisation must not re-introduce clipping: `TP=-1.5` handles this
- The filter should be skipped (logged as a warning, not an error) if
  ffmpeg is not available, to keep the local/mock TTS path working

## Files affected

`src/tts/tts_orchestrator.py`
