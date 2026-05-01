# Repository

Persistence layer for caching fully-parsed ``Book`` models.

- `BookRepository` (ABC) — `save(book, book_id)` / `load(book_id)` / `exists(book_id)` — abstract interface so the storage backend can be swapped (filesystem today, database later) without changing callers
- `FileBookRepository` — file-based implementation; persists `Book.to_dict()` as JSON to `{base_dir}/{book_id}/book.json`; `base_dir` defaults to `./books/`
- `book_id` helper (`generate_book_id(metadata)`) — derives a stable, human-readable directory name from `{Title} - {Author}` with filesystem-unsafe characters replaced by `-`

**Used by**: `AIProjectGutenbergWorkflow` to skip redundant AI calls on repeat runs.  The `--reparse` CLI flag forces a fresh parse when needed.

### workflows/

End-to-end processing orchestration.

- `Workflow` (ABC) - `run(url: str, start_chapter: int = 1, end_chapter: int | None = None, reparse: bool = False) -> Book`
- `ProjectGutenbergWorkflow` - Static parsing only (no AI beatation)
- `AIProjectGutenbergWorkflow` - AI section beatation workflow; takes a `BookSource` (encapsulates download + parse + cache) and a `BookSectionParser` (for AI beatation)
- `TTSProjectGutenbergWorkflow` - Full pipeline: download, AI-parse, voice assign, TTS synthesise

All three concrete workflows share the `run(url, start_chapter=1, end_chapter=None, reparse=False)` signature.
`end_chapter=None` means all chapters; `start_chapter` and `end_chapter` are
1-based inclusive range parameters. When a cached partial book exists and
`reparse=False`, the workflow auto-resumes from the last cached chapter.

**AI Workflow Steps**:

1. Call `BookSource.get_book_for_beatation(url, start_chapter, end_chapter, reparse)` to obtain a `BookParseContext` (contains: `book` with registries, `chapters_to_parse`, and `content`)
2. For each chapter in `chapters_to_parse`:
   For each section in chapter:
   - Pass all preceding sections to `AISectionParser` (parser caps to `context_window`, default 5)
   - Call `AISectionParser.parse(section, registry, context_window, scene_registry=scene_registry)`
   - Thread updated character and scene registries to next section
   - After each chapter: flush to repository via `BookSource` (if one was provided)
3. Return `Book` with chapters from `start_chapter` to `end_chapter`, populated `character_registry`, and `scene_registry`


**TTS Workflow Steps**:

1. Run `AIProjectGutenbergWorkflow.run(url, start_chapter, end_chapter)` to get the parsed `Book`
2. Assign ElevenLabs voices via `VoiceAssigner.assign(registry)`
3. Call `AudioOrchestrator.synthesize_chapter()` for every chapter in the book
4. Return the `Book` (audio files are a side-effect written to `{books_dir}/{book_id}/audio/`)

### audio/

TTS provider abstractions and synthesis orchestration.

- `TTSProvider` (ABC) — `synthesize(text, voice_id, output_path, emotion=None, previous_text=None, next_text=None)` / `get_available_voices()`
- `ElevenLabsProvider` — v2 SDK implementation (`client.text_to_speech.convert`); uses `eleven_multilingual_v2` model (supports `previous_text`/`next_text` context); model capabilities are gated by `_MODEL_CAPS` (inline tags and ALL-CAPS emphasis on v3 only, context params on v2 only); lazy client init
- `VoiceEntry` — dataclass wrapping an ElevenLabs voice (`voice_id`, `name`, `labels`)
- `VoiceAssigner` — deterministic voice assignment for a `CharacterRegistry`; accepts a `TTSProvider` (calls `get_voices()` at construction); narrator first, others matched by `sex`/`age`; optionally accepts an `ElevenLabsVoiceRegistry` for bespoke voice design
- `VoiceDesigner` (`voice_designer.py`) — `design_voice(description, character_name, client)` calls ElevenLabs Voice Design API (create-previews then create-voice) to produce a permanent `voice_id` from a text description
- `BeatContextResolver` — resolves per-beat TTS context: same-character text continuity (`previous_text`/`next_text`), request-ID sliding windows, and scene-based voice modifier deltas (additive on top of emotion presets); used by `AudioOrchestrator`
- `BeatSynthesizer` (`beat_synthesizer.py`) — owns individual beat TTS provider calls
- `AudioAssembler` (`audio_assembler.py`) — audio post-processing: silence insertion, ffmpeg stitching, ambient mixing, sound effect insertion (methods are stubs pending extraction from `AudioOrchestrator`)
- `AudioOrchestrator` — synthesises all speakable beats (NARRATION, DIALOGUE, SOUND_EFFECT) in a chapter; delegates context resolution to `BeatContextResolver`; interleaves silence clips between beats (duration varies by speaker boundary type); SOUND_EFFECT beats are synthesised via `SoundEffectProvider` when `sound_effects_enabled` is True; stitches output via ffmpeg

**Voice assignment algorithm**: The narrator always receives the first voice.  Non-narrator characters with `voice_design_prompt` set get a bespoke voice via the Voice Design API (falling back to demographic matching on any API error).  Remaining characters receive the highest-scoring unassigned voice (score = number of matching `sex`/`age` labels).  Ties broken by pool position; voices cycle when exhausted.

### main.py (root)

CLI entry point.

**Current interface**:

```bash
# Parse only — download, AI-beat, output JSON
python main.py <gutenberg_url> [-o output.json]

# Full TTS pipeline — download, AI-beat, assign voices, synthesise Chapter 1
python main.py <gutenberg_url> --tts
```

Without `--tts`: Creates a `ProjectGutenbergWorkflow`, runs it with all chapters, and outputs JSON to stdout or a file.

With `--tts`: Creates an `AIProjectGutenbergWorkflow`, runs it for Chapter 1, assigns voices via `VoiceAssigner` (which fetches voices from the configured `TTSProvider`), synthesises beats via `AudioOrchestrator`, and prints the path to `output/{chapter_title}/chapter.mp3`.  Requires `FISH_AUDIO_API_KEY` environment variable (Fish Audio is the default TTS provider); exits non-zero with a clear message if absent.

**Preferred entry point**: `scripts/run_workflow.py` is the recommended CLI for most uses:

```bash
# AI parse (default) on chapters 1-3
python scripts/run_workflow.py --url <url> --start-chapter 1 --end-chapter 3 --workflow ai

# Static parse only
python scripts/run_workflow.py --url <url> --workflow parse

# Full TTS pipeline
python scripts/run_workflow.py --url <url> --workflow tts
```

**Note**: `main.py` does NOT use `Config.from_cli()`. It has a minimal argparse setup. The extensive `Config` class is only used for AWS credentials inside workflows.
