# US-012 — Background Music

## Goal

Enable the AI parser to detect music cues in the narrative and generate background music from free-form descriptions. Music becomes part of the timeline as MUSIC segments, starting at specific moments and continuing until another music cue or an explicit end. This allows the emotional arc of a scene to be underscored with music that matches the moment—tense strings building during a confrontation, gentle piano during a quiet reflection, upbeat themes for comedic exchanges.

## Problem

Audiobooks today rely on voice alone to convey emotion. Film and television use music to prime the emotional response before dialogue begins. A well-placed 30-second music loop under a tense scene amplifies the prose far beyond what TTS voice modulation achieves. Current design has no mechanism for music—no representation in the domain model, no AI detection, no generation pipeline.

The old design (music_mood as a per-chapter enum field) was too rigid: chapter-level granularity misses scene-level mood shifts, predefined mood enums cannot capture nuanced emotional beats, and the LLM has no way to express what the music should sound like for a specific moment.

## Acceptance criteria

1. **SegmentType.MUSIC added to domain model**
   - File: `src/domain/models.py`
   - Add `MUSIC = "music"` to the `SegmentType` enum (alongside NARRATION, DIALOGUE, ILLUSTRATION, COPYRIGHT, OTHER)
   - MUSIC segments have:
     - `segment_type: SegmentType.MUSIC`
     - `text: str` — free-form music description for the generation API (e.g., "tense orchestral strings building slowly", "gentle piano, melancholic, slow tempo", "upbeat comedic theme, light and bouncy")
     - `character_id: Optional[str] = None` — always None for MUSIC segments
     - `scene_id: Optional[str] = None` — inherited from context (same as other segment types)
     - All other segment fields (emotion, voice_stability, voice_style, voice_speed, sound_effect_description) are None for MUSIC segments

2. **AI parser detects music cues and outputs MUSIC segments**
   - File: `src/ai/prompts/segment_prompt.py` (or inline in `src/parsers/ai_section_parser.py` if prompt is not extracted)
   - Update the LLM prompt to instruct:
     - Detect moments where background music should start based on narrative cues (emotional shifts, scene changes, tension building, etc.)
     - Output a MUSIC segment with a natural-language description of the desired music in the `text` field
     - Music continues until either another MUSIC segment appears (which replaces it) or the AI determines music should stop (output a MUSIC segment with `text: "silence"` or similar convention to mark explicit end)
   - The AI returns MUSIC segments in the same JSON structure as other segments
   - MUSIC segments appear in the segment list at the position where the music should start
   - Example output:
     ```json
     {
       "segments": [
         {"segment_type": "narration", "text": "The door creaked open.", "character_id": "narrator"},
         {"segment_type": "music", "text": "tense orchestral strings building slowly, low rumble"},
         {"segment_type": "dialogue", "text": "Who's there?", "character_id": "elizabeth_bennet"},
         ...
       ]
     }
     ```

3. **AudioOrchestrator handles MUSIC segments during synthesis**
   - File: `src/tts/audio_orchestrator.py`
   - In `_synthesise_segments()`, skip MUSIC segments (they are not synthesized to TTS audio)
   - Track MUSIC segments separately as timeline markers indicating where music should start/stop
   - After stitching speech segments, call music provider to generate music audio from each MUSIC segment's `text` field
   - Mix generated music under the speech audio starting at the MUSIC segment's timeline position
   - Music continues until the next MUSIC segment or end of chapter
   - Music is mixed at -22 dB beneath speech (same level as existing ambient sound)
   - Music fades in over first 3 seconds and fades out over last 3 seconds (or at transitions to new music cues)

4. **MusicProvider.generate() called by AudioOrchestrator**
   - File: `src/tts/audio_orchestrator.py`
   - Add `music_provider: Optional[MusicProvider] = None` to `__init__()` constructor
   - Add `music_enabled: bool = False` to `FeatureFlags` in `src/config/feature_flags.py`
   - When `music_enabled` is True and `music_provider` is not None, generate and mix music
   - Call `music_provider.generate(description, output_path, duration_seconds)` for each MUSIC segment
   - Cache generated music files in `output_dir/music/{hash}.mp3` where `{hash}` is SHA256 of the description text
   - Duration is computed from timeline: distance to next MUSIC segment or end of chapter

5. **ffmpeg mixing pipeline for music**
   - File: `src/tts/audio_orchestrator.py` (or delegate to `audio_assembler.py` if refactored)
   - Music is mixed after stitching speech segments (same pattern as ambient sound)
   - Use ffmpeg filter_complex to:
     - Loop music track to required duration
     - Apply volume adjustment (-22 dB)
     - Apply afade (3s fade-in at start, 3s fade-out at end or at transition to next music cue)
     - Mix under speech using `amix` filter
   - If multiple music segments exist in one chapter, use `acrossfade` between them (5s crossfade duration, same as ambient)
   - Music is mixed in the same ffmpeg pass as ambient sound if both are present (speech + ambient + music → one output)

6. **MUSIC segments serialized in Book.to_dict()**
   - File: `src/domain/models.py`
   - No changes needed—existing `Book.to_dict()` already serializes all segments including new SegmentType.MUSIC
   - Verify `Book.from_dict()` correctly reconstructs MUSIC segments (SegmentType enum handling already exists)

7. **make verify produces output.json with MUSIC segments**
   - Run `make verify` on a test book (e.g., Pride & Prejudice first 3 chapters)
   - Confirm output.json contains segments with `"segment_type": "music"` and free-form text descriptions
   - Confirm text descriptions are natural-language music prompts (not enum values)

## Out of scope

- Music generation API integration (Suno AI, ElevenLabs Music, etc.) — this spec only defines the domain model and orchestrator interface; actual provider implementations are separate specs (US-028 already exists for Suno)
- Dynamic tempo/key matching to speech pace
- Music volume automation (ducking during dialogue vs narration)
- Per-scene music inheritance (music does not automatically persist across scene boundaries unless explicitly continued by the LLM)
- Retroactive music insertion (music cues must be detected during initial AI parsing; no post-processing pass to add music later)
- Music mood presets or enums — ALL music descriptions are free-form text prompts

## Key design decisions

### Music as a segment type (not a chapter field)

Music is not a property of a chapter—it's a timeline event with a start position. By making it a segment type, we give the LLM fine-grained control over when music starts and stops, and we represent it in the same data structure as speech. This eliminates the need for a separate music-cue data structure.

### Free-form descriptions (no enums)

Predefined mood enums (TENSE, SAD, HAPPY, etc.) cannot capture the nuance of a specific moment. "Tense" means different things in a thriller vs a romance. Free-form text descriptions (e.g., "tense orchestral strings building slowly, low rumble, thriller score") give the LLM expressive power and the music generation API flexibility. This mirrors the design of sound_effect_description and ambient_prompt—both are free-form natural-language strings.

### Music mixed at -22 dB (same as ambient)

Music competes with speech more than ambient noise does (melody and rhythm draw attention). -22 dB keeps it subliminal. If both ambient and music are present, the hierarchy is: speech > ambient > music. The orchestrator applies both in one ffmpeg pass to avoid multiple re-encoding steps.

### AI detects music cues (no manual annotation)

The LLM already detects scene changes, emotions, sound effects, and ambient prompts. Asking it to also detect music cues is consistent with the design philosophy: leverage the AI's understanding of narrative structure rather than requiring manual annotation or predefined rules.

### Music continues until explicit change

A MUSIC segment at position N starts music at that point in the timeline. The music continues until either:
- Another MUSIC segment appears (replacing the current music with a new cue)
- The LLM outputs a MUSIC segment with `text: "silence"` to mark an explicit end
- The chapter ends

This avoids needing a separate "music_end" segment type. The convention `text: "silence"` is simple and unambiguous.

### 3s fade in/out

Hard music cuts are jarring. A 3s fade is imperceptible to the listener but eliminates the click. This matches the fade duration used for ambient sound and SFX. ffmpeg's `afade` filter handles this in one argument.

## Files changed (expected)

| File | Change |
|---|---|
| `src/domain/models.py` | Add `MUSIC = "music"` to `SegmentType` enum |
| `src/ai/prompts/segment_prompt.py` (or `src/parsers/ai_section_parser.py`) | Update LLM prompt to detect music cues and output MUSIC segments with free-form descriptions |
| `src/tts/audio_orchestrator.py` | Add music timeline tracking, call `music_provider.generate()`, mix music under speech with fade in/out |
| `src/config/feature_flags.py` | Add `music_enabled: bool = False` field |

## Implementation notes

- MUSIC segments are NOT synthesized by the TTS provider—they are timeline markers that trigger music generation
- The orchestrator skips MUSIC segments in `_synthesise_segments()` (same as ILLUSTRATION/COPYRIGHT/OTHER)
- Music generation happens after speech stitching (same pattern as ambient)
- The `MusicProvider` interface already exists (`src/tts/music_provider.py`) and has the required `generate(prompt, output_path, duration_seconds)` signature
- The Suno AI music provider (US-028) is already implemented and can be used as the concrete implementation
- Music segments must pass through the existing segment filtering logic unchanged (they are narratable in the sense that they affect the output, but they are not spoken)
- The `is_narratable` property on Segment should return False for MUSIC segments (add to the skip list alongside ILLUSTRATION/COPYRIGHT/OTHER)
