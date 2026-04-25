# Feature Flags

All features default to enabled. Toggle them via CLI flags or constructor parameters.

## Available Features

- **ambient_enabled** — Generates ambient background audio per scene at -28 dB
- **sound_effects_enabled** — Inserts diegetic sound effects into silence gaps
- **emotion_enabled** — Applies emotion tags to voice synthesis
- **voice_design_enabled** — Calls Voice Design API for custom character voices; falls back to demographic matching if disabled
- **scene_context_enabled** — Applies scene-based voice modifiers (acoustic environment changes)
- **debug** — Keeps individual segment MP3 files instead of deleting them after stitching

## CLI Flags

```bash
# Toggle features
--enable-ambient / --disable-ambient
--enable-sound-effects / --disable-sound-effects
--enable-emotion / --disable-emotion
--enable-voice-design / --disable-voice-design
--enable-scene-context / --disable-scene-context
--debug

# Examples
python main.py --workflow tts --url <url> --start-chapter 1 --end-chapter 3
python main.py --workflow tts --url <url> --disable-ambient --disable-sound-effects
python main.py --workflow ai --url <url> --start-chapter 1 --end-chapter 1 --refresh
```
