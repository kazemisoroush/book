# Storage

The whole pipeline writes through two layers:

- [Storage](storage.py): primitive key-and-bytes object store. One backend per medium ([LocalStorage](local_storage.py) today, an S3 backend later).
- [AudioStore](audio_store.py) and the existing [BookRepository](../repository/book_repository.py) / [AIArtifactStore](../repository/ai_artifact_store.py): domain-shaped stores that take value objects and own the layout decisions.

Callers never see a storage key. They pass a value object; the store decides where it goes.

## Value objects

[`objects.py`](objects.py) defines the dataclasses callers use. Payload-carrying objects (`TTSBeat`, `TTSChunk`, `SFXBeat`) carry the bytes and expose a `.ref` property for identity. Identity-only refs (`TTSBeatRef`, `SilenceClipRef`, `MixOutputRef`, `TrimStepRef`, `VoiceRequestRef`) are used for `has_X` / `open_X_for_*` calls. `APIRequest` captures one outbound API call.

## AudioStore

The store every audio writer talks to. Typed methods, never a key argument:

```python
class AudioStore:
    has_tts_beat(ref) / save_tts_beat(beat, api_request=None) / open_tts_beat(ref)
    has_tts_chunk(ref) / save_tts_chunk(chunk, api_request=None) / list_tts_chunks(...)
    has_tts_provider_outputs(book_id, provider)

    has_sfx_beat(ref) / save_sfx_beat(beat) / open_sfx_beat(ref, mode)

    has_silence_clip(ref) / open_silence_clip(ref, mode)

    open_mix_output(ref) / with_concat_manifest(ref, lines) -> Path

    open_trim_step(ref, mode) / open_final_trimmed_beat(ref) / delete_trim_artifacts(beat_ref)

    save_voice_request(ref, request) / save_shared_voice_search(request)
```

`open_X` returns a context manager yielding a real filesystem `Path` for tools that need one (ffmpeg, ffprobe, `torchaudio.save`). On a future S3 backend the context manager would download on entry and upload on exit; callers do not change.

API request sidecars are not a separate store. A TTS or character call passes its `APIRequest` to the same `save_X` method that writes the audio; `AudioStore` writes the JSON sidecar next to the artifact.

## How to add an S3 backend

Implement [Storage](storage.py) once and swap the constructor in [workflow_factory](../workflows/workflow_factory.py). `AudioStore`, the repository classes, every provider, and `MixWorkflow` are untouched.

## How to add a new artifact type

Define one ref dataclass and (if it carries bytes) one payload dataclass in [`objects.py`](objects.py). Add `save_X` / `has_X` / `open_X` to [`audio_store.py`](audio_store.py). The caller imports the new type and uses the new method. No string keys.
