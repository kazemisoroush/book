# TTS

Text-to-speech synthesis for narration and dialogue beats. Owns the swappable TTS provider abstraction plus voice assignment, voice design, and per-beat synthesis context (continuity, scene modifiers, request-ID windows).

## TTSProvider

`synthesize(text, voice_id, output_path, emotion=None, previous_text=None, next_text=None)` / `get_available_voices()`

### Implementations

- `ElevenLabsProvider` — v2 SDK implementation (`client.text_to_speech.convert`); uses `eleven_multilingual_v2` model (supports `previous_text`/`next_text` context); model capabilities are gated by `_MODEL_CAPS` (inline tags and ALL-CAPS emphasis on v3 only, context params on v2 only); lazy client init

## VoiceEntry

Dataclass wrapping an ElevenLabs voice (`voice_id`, `name`, `labels`)

## VoiceAssigner

Deterministic voice assignment for a `CharacterRegistry`; accepts a `TTSProvider` (calls `get_voices()` at construction); narrator first, others matched by `sex`/`age`; optionally accepts an `ElevenLabsVoiceRegistry` for bespoke voice design.

**Voice assignment algorithm**: The narrator always receives the first voice.  Non-narrator characters with `voice_design_prompt` set get a bespoke voice via the Voice Design API (falling back to demographic matching on any API error).  Remaining characters receive the highest-scoring unassigned voice (score = number of matching `sex`/`age` labels).  Ties broken by pool position; voices cycle when exhausted.

## VoiceDesigner

`voice_designer.py` — `design_voice(description, character_name, client)` calls ElevenLabs Voice Design API (create-previews then create-voice) to produce a permanent `voice_id` from a text description.

## BeatContextResolver

Resolves per-beat TTS context: same-character text continuity (`previous_text`/`next_text`), request-ID sliding windows, and scene-based voice modifier deltas (additive on top of emotion presets); used by `AudioOrchestrator`.

## BeatSynthesizer

`beat_synthesizer.py` — owns individual beat TTS provider calls.
