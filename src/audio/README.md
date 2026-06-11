# Audio

Audio synthesis and post-processing for a book chapter. Per-beat synthesis lives in `tts/` (driven by `TTSWorkflow`); chapter stitching with interleaved silence happens in `src/workflows/mix_workflow.py` (driven by `MixWorkflow`).

## AudioTrimmer

`audio_trimmer.py` — abstract base for any one-purpose transform that reads a beat MP3 and writes another (single `trim(input_path, output_path)` method). Mirrors the `BeatTrimmer` ABC in `src/trimmers/` but for audio rather than text.

### StartAndEndBeatSilenceTrimmer

`start_and_end_beat_silence_trimmer.py` — strips leading and trailing vendor-baked silence from a synthesised beat MP3 via `ffmpeg silenceremove`, applying tiny fade-in and fade-out so the cut doesn't click. Internal silences (comma pauses, breaths, sentence endings) are preserved via the reverse-trim-reverse recipe. Used by `MixWorkflow` before concat when `FeatureFlags.beat_silence_trimming_enabled` is True. The raw vendor MP3 is preserved; the trimmer writes a sibling `beat_NNNN.trimmed.mp3`, the stitch consumes it, and the sibling is deleted on successful stitch.

## audio_duration

`audio_duration.py` — small `ffprobe`-backed helper that returns the duration of an MP3 in seconds.
