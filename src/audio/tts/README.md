# TTS

Text-to-speech synthesis for narration and dialogue beats. Owns the swappable TTS provider abstraction plus voice assignment, voice design, and per-beat synthesis context (continuity, scene modifiers, request-ID windows).

## TTSProvider

`synthesize(text, voice_id, output_path, emotion=None, previous_text=None, next_text=None)` / `get_available_voices()`

### ElevenLabsV2Provider

ElevenLabs `eleven_multilingual_v2` model. Text passes through unchanged (the model speaks inline tags verbatim, so `beat.emotion` is not consumed at synthesis time). Honors `beat.voice_settings` when set, otherwise uses a fixed neutral preset. Forwards `previous_text` / `next_text` / `previous_request_ids` to the SDK for prosody and acoustic continuity. Default provider returned by the workflow factory.

### ElevenLabsV3Provider

ElevenLabs `eleven_v3` model. Wraps free-form `beat.emotion` as the inline audio tag `[emotion] text` (`None` and `"neutral"` skip the tag). Honors `beat.voice_settings` when set, otherwise uses a fixed permissive preset. Does not forward `previous_text` / `next_text` / `previous_request_ids` (v3 returns 400 on them). Available but not selected by the default factory.

### FishAudioTTSProvider

TBA

### StubTTSProvider

TBA

### VibeVoiceTTSProvider

TBA

## BeatContext

TBA

## BeatContextResolver

Resolves per-beat TTS context: same-character text continuity (`previous_text`/`next_text`), request-ID sliding windows, and scene-based voice modifier deltas (additive on top of emotion presets); used by `TTSWorkflow`.

## BeatSynthesizer

`beat_synthesizer.py` — owns individual beat TTS provider calls.

## VoiceEntry

Dataclass wrapping an ElevenLabs voice (`voice_id`, `name`, `labels`).

## VoiceAssigner

Deterministic voice assignment for a `CharacterRegistry`; accepts a `TTSProvider` (calls `get_voices()` at construction); narrator first, others matched by `sex`/`age`; optionally accepts an `ElevenLabsVoiceRegistry` for bespoke voice design.

**Voice assignment algorithm**: The narrator always receives the first voice.  Non-narrator characters with `voice_design_prompt` set get a bespoke voice via the Voice Design API (falling back to demographic matching on any API error).  Remaining characters receive the highest-scoring unassigned voice (score = number of matching `sex`/`age` labels).  Ties broken by pool position; voices cycle when exhausted.

## ElevenLabsVoiceRegistry

TBA

## voice_designer

Module-level helper: `design_voice(description, character_name, client)` calls ElevenLabs Voice Design API (create-previews then create-voice) to produce a permanent `voice_id` from a text description.

## audio_trimmer/

Sub-package of one-purpose transforms over a synthesised beat MP3, parallel to `src/trimmers/` on the text side.

### AudioTrimmer

`audio_trimmer.py` — abstract base. Public `trim(input_path, output_path)` skips when *output_path* already holds a non-empty file; subclasses implement the actual work in `_trim`.

### AudioTrimmerPipeline

`audio_trimmer_pipeline.py` — owns the trim-chain naming convention and the trimmed-sibling lifecycle. `apply(beat_pairs)` runs every trimmer over every beat (intermediate steps land at `{beat}.trim_step_N.mp3`; the last step writes the final `{beat}.trimmed.mp3`). `cleanup(applied, original)` deletes every sibling produced by `apply` and is a no-op when the pipeline is empty. MixWorkflow holds one of these and calls into it before / after each chapter stitch.

### StartAndEndBeatSilenceTrimmer

`start_and_end_beat_silence_trimmer.py` — strips leading and trailing vendor-baked silence from a synthesised beat MP3 via `ffmpeg silenceremove`, applying tiny fade-in and fade-out so the cut doesn't click. Internal silences (comma pauses, breaths, sentence endings) are preserved via the reverse-trim-reverse recipe. Used by `MixWorkflow` before concat. The raw vendor MP3 is preserved; the trimmer writes a sibling `beat_NNNN.trimmed.mp3`, the stitch consumes it, and the sibling is deleted on successful stitch.

### PeakLevelTrimmer

`peak_level_trimmer.py` — runs `ffmpeg highpass` to roll off low-end rumble, measures the beat's peak via `ffmpeg volumedetect`, then applies a flat `volume` gain so every beat lands at the same peak ceiling (default `-1` dBTP). Runs after `StartAndEndBeatSilenceTrimmer` in the default mix pipeline so the seams between beats sound level-matched without touching dynamics. Designed for short clips, unlike EBU R128 loudnorm which behaves erratically on per-beat audio. Defaults: `peak_target_db=-3.0`, `highpass_hz=80`. The target sits 3 dB under full scale so MP3 re-encode rounding stays under 0 dBFS.
