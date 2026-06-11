# Audio

Audio synthesis and post-processing for a book chapter. Per-beat synthesis lives in `tts/` (driven by `TTSWorkflow`); chapter stitching with interleaved silence happens in `src/workflows/mix_workflow.py` (driven by `MixWorkflow`).

## SilenceTrimmer

`silence_trimmer.py` — strips leading and trailing vendor-baked silence from a synthesised beat MP3 via `ffmpeg silenceremove`, applying tiny fade-in and fade-out so the cut doesn't click. Used by `MixWorkflow` before concat when `FeatureFlags.beat_silence_trimming_enabled` is True. The raw vendor MP3 is preserved; the trimmer writes a sibling `beat_NNNN.trimmed.mp3`, the stitch consumes it, and the sibling is deleted on successful stitch.

## audio_duration

`audio_duration.py` — small `ffprobe`-backed helper that returns the duration of an MP3 in seconds.
