# Audio

Audio synthesis and post-processing for a book chapter. Per-beat synthesis and post-synthesis transforms live in `tts/` (driven by `TTSWorkflow`); chapter stitching with interleaved silence happens in `src/workflows/mix_workflow.py` (driven by `MixWorkflow`).

## audio_duration

`audio_duration.py` — small `ffprobe`-backed helper that returns the duration of an MP3 in seconds.
