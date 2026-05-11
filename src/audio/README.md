# Audio

Audio synthesis and post-processing for a book chapter. Coordinates per-beat synthesis, silence insertion, ambient mixing, sound effect insertion, and final ffmpeg stitching into a chapter MP3.

## AudioAssembler

`audio_assembler.py` — audio post-processing: silence insertion, ffmpeg stitching, ambient mixing, sound effect insertion (methods are stubs pending extraction from `AudioOrchestrator`)

## AudioOrchestrator

Synthesises all speakable beats (NARRATION, DIALOGUE, SOUND_EFFECT) in a chapter; delegates context resolution to `BeatContextResolver`; interleaves silence clips between beats (duration varies by speaker boundary type); SOUND_EFFECT beats are synthesised via `SoundEffectProvider` when `sound_effects_enabled` is True; stitches output via ffmpeg
