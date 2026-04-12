# Architecture

## Overview

The audiobook generator is built as a layered pipeline that transforms Project Gutenberg HTML books into structured, character-segmented data ready for multi-voice TTS synthesis.

## Layer Model

The codebase is organized into functional modules, not strict layers. Dependencies flow as follows:

```
config → domain → (ai, parsers, downloader, repository, audio, workflows) → main.py
```

No `types/`, `adapters/`, `services/`, or `cli/` directories exist. The implementation uses a pragmatic module structure optimized for clarity and testability.

## Module Responsibilities

### config/

Configuration management. All options support both CLI arguments and environment variables.

- `config.py` - `Config` and `AWSConfig` dataclasses
- `Config.from_env()` - Load from environment variables
- `Config.from_cli()` - Load from CLI args with env var fallback (not currently used by main.py)

- `feature_flags.py` - `FeatureFlags` dataclass for runtime toggles (ambient sound, sound effects, emotion tags, voice design, scene context)
- `FeatureFlags.from_yaml()` / `FeatureFlags.from_json()` - Load feature toggles from config files
- `FeatureFlags.to_dict()` / `FeatureFlags.from_dict()` - Serialize/deserialize feature toggles

**Currently**: `AWSConfig` used for Bedrock credentials; `FeatureFlags` used to toggle end-to-end features at runtime.

### domain/

Core data models representing books, chapters, sections, segments, and characters.

- `Book` - Top-level container (metadata + content + character_registry + scene_registry); has `to_dict()` / `from_dict()` for full round-trip serialisation including both registries
- `BookMetadata` - Bibliographic information
- `BookContent` - Chapters and sections
- `Chapter` - Numbered chapter with title and sections
- `Section` - A paragraph, optionally segmented
- `Segment` - A piece of narration, dialogue, or sound effect; carries `emotion: Optional[str]` (a freeform lowercase auditory tag, e.g. `"whispers"`, `"laughs harder"`), optional `voice_stability`/`voice_style`/`voice_speed` floats (LLM-provided), `scene_id: Optional[str]` referencing a `Scene` in the book's `SceneRegistry`, and `sound_effect_detail: Optional[str]` (for SOUND_EFFECT segments — a detailed sound effect generation prompt, e.g. `"4 firm knocks on a heavy old wooden door, echoing in a stone hallway"`)
- `SegmentType` - Enum: NARRATION, DIALOGUE, SOUND_EFFECT, ILLUSTRATION, COPYRIGHT, OTHER
- `Character` - A voice character (narrator or speaker); fields: `character_id`, `name`, `description`, `is_narrator`, `sex`, `age`; has `to_dict()` / `from_dict()` for serialisation; `voice_design_prompt` is a computed property derived from `age`, `sex`, and `description`
- `Scene` - Frozen value object describing an acoustic environment; fields: `scene_id`, `environment`, `acoustic_hints`, `voice_modifiers` (LLM-provided deltas: `stability_delta`, `style_delta`, `speed`), `ambient_prompt` (natural-language description of background sound), `ambient_volume` (mix level in dB)
- `AIPrompt` - Frozen value object for structured LLM prompts with cache-friendly builder methods (`build_static_portion`, `build_dynamic_portion`, `build_full_prompt`); fields: `static_instructions`, `book_context`, `character_registry`, `surrounding_context`, `scene_registry`, `text_to_segment`
- `SceneRegistry` - Registry of all scenes in a book; mirrors `CharacterRegistry` pattern (`upsert`, `get`, `all`, `to_dict`/`from_dict`)
- `CharacterRegistry` - Registry of all characters in a book

**Key invariant**: Every segment has a `character_id`. Narration segments always use `"narrator"`. This ensures no null speaker bugs.

### ai/

AI provider abstraction for LLM calls.

- `AIProvider` (ABC) - `generate(prompt: AIPrompt, max_tokens) -> str`
- `AWSBedrockProvider` - AWS Bedrock Claude implementation; accepts optional `token_tracker` kwarg
- `TokenTracker` - Tracks per-call and cumulative token usage and estimated cost across Bedrock calls
- `ModelPricingEntry` / `MODEL_PRICING` / `get_pricing()` - Static pricing table and lookup for cost estimation
- `CallRecord` - Immutable record of a single invocation (model ID, token counts, estimated cost)

**Used by**: `AISectionParser` to segment dialogue and identify speakers.

### parsers/


- `BookSource` (ABC) - Encapsulates download → parse → cache pipeline; `get_book(url)` returns a complete Book; `get_book_for_segmentation(url, start_chapter, end_chapter, reparse)` returns a `BookParseContext` with uncached chapters
- `ProjectGutenbergBookSource` - Concrete implementation composing a downloader, metadata parser, content parser, and optional repository
Parsers for extracting structured data from HTML and using AI to segment text.

- `BookMetadataParser` (ABC)
- `BookContentParser` (ABC)
- `BookSectionParser` (ABC)
- `StaticProjectGutenbergHTMLMetadataParser` - Extracts title, author, etc. from HTML
- `StaticProjectGutenbergHTMLContentParser` - Extracts chapters/sections from HTML
- `AISectionParser` - AI-powered dialogue segmentation, speaker identification, and character description formation
- `text_sanitizer` - Pure function `sanitize_segment_text(text)` that strips trailing non-terminal punctuation and normalizes whitespace; called at segment creation time to prevent TTS artefacts

**AI Section Parser Flow**:

1. Receives a `Section`, current `CharacterRegistry`, and optional `context_window` (up to `context_window` preceding sections, default 5)
2. Builds a prompt including the registry (for speaker reuse and current descriptions) and context (for pronoun/speaker resolution); prompt includes instruction to strip trailing non-terminal punctuation from segment text
3. Calls `AIProvider.generate()`
4. Parses JSON response into `Segment` list, new `Character` entries (including inferred `sex`, `age`, and `description`), `character_description_updates` for existing characters, and an optional `Scene` (environment, acoustic hints, voice modifiers)
5. Applies `sanitize_segment_text()` to each segment's text field as a safety net (strips trailing commas, semicolons, em-dashes, etc.)
6. Filters out non-narratable segments (`segment_type` not in {NARRATION, DIALOGUE}) so cached output contains only speakable content
7. Upserts new characters into the character registry; upserts detected scene into the scene registry; stamps `scene_id` on each segment
8. Returns `(segments, updated_character_registry)`

**Context Window**: The parser receives preceding sections from the same chapter as read-only context (capped to `context_window`, default 5). The workflow passes all preceding sections; the parser caps the list internally. Noise-only sections (OTHER/ILLUSTRATION/COPYRIGHT) are filtered out before the cap is applied, so the window always contains up to 5 substantive sections. This allows the AI to resolve ambiguous speakers (e.g., "he replied") by following conversational turn-taking.

### downloader/

Downloads books from external sources. Implements disk caching to avoid redundant network requests.

- `BookDownloader` (ABC) - `download(url) -> str`
- `ProjectGutenbergHTMLBookDownloader` - Downloads zip files from Project Gutenberg, extracts HTML; skips download if HTML already exists on disk from a previous run

**Output**: Books are downloaded to `books/{book_id}/` directory.
**Caching**: If the HTML file already exists on disk, the downloader returns the cached content without making a network request.


### repository/

Persistence layer for caching fully-parsed ``Book`` models.

- `BookRepository` (ABC) — `save(book, book_id)` / `load(book_id)` / `exists(book_id)` — abstract interface so the storage backend can be swapped (filesystem today, database later) without changing callers
- `FileBookRepository` — file-based implementation; persists `Book.to_dict()` as JSON to `{base_dir}/{book_id}/book.json`; `base_dir` defaults to `./books/`
- `book_id` helper (`generate_book_id(metadata)`) — derives a stable, human-readable directory name from `{Title} - {Author}` with filesystem-unsafe characters replaced by `-`

**Used by**: `AIProjectGutenbergWorkflow` to skip redundant AI calls on repeat runs.  The `--reparse` CLI flag forces a fresh parse when needed.

### workflows/

End-to-end processing orchestration.

- `Workflow` (ABC) - `run(url: str, start_chapter: int = 1, end_chapter: int | None = None, reparse: bool = False) -> Book`
- `ProjectGutenbergWorkflow` - Static parsing only (no AI segmentation)
- `AIProjectGutenbergWorkflow` - AI section segmentation workflow; takes a `BookSource` (encapsulates download + parse + cache) and a `BookSectionParser` (for AI segmentation)
- `TTSProjectGutenbergWorkflow` - Full pipeline: download, AI-parse, voice assign, TTS synthesise

All three concrete workflows share the `run(url, start_chapter=1, end_chapter=None, reparse=False)` signature.
`end_chapter=None` means all chapters; `start_chapter` and `end_chapter` are
1-based inclusive range parameters. When a cached partial book exists and
`reparse=False`, the workflow auto-resumes from the last cached chapter.

**AI Workflow Steps**:

1. Call `BookSource.get_book_for_segmentation(url, start_chapter, end_chapter, reparse)` to obtain a `BookParseContext` (contains: `book` with registries, `chapters_to_parse`, and `content`)
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
- `VoiceAssigner` — deterministic voice assignment for a `CharacterRegistry`; narrator first, others matched by `sex`/`age`; optionally accepts an ElevenLabs client to design bespoke voices for characters with `voice_design_prompt`
- `VoiceDesigner` (`voice_designer.py`) — `design_voice(description, character_name, client)` calls ElevenLabs Voice Design API (create-previews then create-voice) to produce a permanent `voice_id` from a text description
- `SegmentContextResolver` — resolves per-segment TTS context: same-character text continuity (`previous_text`/`next_text`), request-ID sliding windows, and scene-based voice modifier deltas (additive on top of emotion presets); used by `AudioOrchestrator`
- `SegmentSynthesizer` (`segment_synthesizer.py`) — owns individual segment TTS provider calls; gates feature flags (emotion, voice design) via `AudioOrchestrator` class constants
- `AudioAssembler` (`audio_assembler.py`) — audio post-processing: silence insertion, ffmpeg stitching, ambient mixing, sound effect insertion (methods are stubs pending extraction from `AudioOrchestrator`)
- `AudioOrchestrator` — synthesises all speakable segments (NARRATION, DIALOGUE, SOUND_EFFECT) in a chapter; delegates context resolution to `SegmentContextResolver`; interleaves silence clips between segments (duration varies by speaker boundary type); SOUND_EFFECT segments are synthesised via `SoundEffectProvider` when `sound_effects_enabled` is True; stitches output via ffmpeg

**Voice assignment algorithm**: The narrator always receives the first voice.  Non-narrator characters with `voice_design_prompt` set get a bespoke voice via the Voice Design API (falling back to demographic matching on any API error).  Remaining characters receive the highest-scoring unassigned voice (score = number of matching `sex`/`age` labels).  Ties broken by pool position; voices cycle when exhausted.

### main.py (root)

CLI entry point.

**Current interface**:

```bash
# Parse only — download, AI-segment, output JSON
python main.py <gutenberg_url> [-o output.json]

# Full TTS pipeline — download, AI-segment, assign voices, synthesise Chapter 1
python main.py <gutenberg_url> --tts
```

Without `--tts`: Creates a `ProjectGutenbergWorkflow`, runs it with all chapters, and outputs JSON to stdout or a file.

With `--tts`: Creates an `AIProjectGutenbergWorkflow`, runs it for Chapter 1, fetches ElevenLabs voices, assigns them via `VoiceAssigner`, synthesises segments via `AudioOrchestrator`, and prints the path to `output/{chapter_title}/chapter.mp3`.  Requires `ELEVENLABS_API_KEY` environment variable; exits non-zero with a clear message if absent.

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

## Data Flow

```
1. URL (e.g., https://www.gutenberg.org/cache/epub/1342/pg1342-h.zip)
   ↓
2. BookSource.get_book_for_segmentation(url, start_chapter, end_chapter, reparse)
   → calls BookDownloader.download(url) → HTML content
   → calls BookMetadataParser.parse(html) → BookMetadata
   → generates book_id from metadata
   → checks BookRepository cache (if reparse=False)
   → calls BookContentParser.parse(html) → BookContent
   → builds CharacterRegistry.with_default_narrator()
   → returns BookParseContext(book, chapters_to_parse, content)
   ↓
3. For each chapter in chapters_to_parse:
     For each section in chapter:
       context_window = all preceding sections in chapter (parser caps to context_window, default 5)
       ↓
       AISectionParser.parse(section, registry, context_window)

         → builds prompt with registry + context
         → calls AIProvider.generate()
         → parses JSON response
         → returns (segments, updated_registry)
         → upserts detected scene into scene_registry
         → stamps scene_id on each segment
       ↓
       section.segments = segments
       registry = updated_registry
   ↓
8. Book(metadata, content, character_registry)
   ↓
8b. Each chapter is flushed to BookRepository after parsing (if available)
   ↓
9. Book.to_dict() → JSON
   ↓
10. Output to stdout or file
```

## Key Abstractions

### Dependency Inversion

All external dependencies (AI, downloader, parsers) are abstracted behind interfaces:

- `AIProvider` - LLM abstraction (currently AWS Bedrock, could be OpenAI, Anthropic Direct, etc.)
- `BookDownloader` - Download source abstraction (currently Gutenberg HTML, could be EPUB, PDF, etc.)
- `BookMetadataParser` / `BookContentParser` / `BookSectionParser` - Parsing abstractions
- `BookRepository` - Persistence abstraction for caching parsed books (currently file-based, could be database-backed)

Workflows depend on these abstractions, not concrete implementations. Factory methods (`Workflow.create()`) wire up the concrete dependencies.

### Character Registry Threading

The `CharacterRegistry` is mutable state threaded through the entire parsing pipeline:

1. Bootstrapped with default narrator before parsing starts
2. Passed to each `AISectionParser.parse()` call
3. AI receives current registry in prompt (to reuse character IDs)
4. AI returns new characters (or updates to existing ones)
5. Registry updated via `upsert()`
6. Updated registry passed to next section

This ensures character IDs are consistent across the entire book. A character discovered in chapter 1 uses the same ID in chapter 10.

### Scene Registry Threading

The `SceneRegistry` follows the same threading pattern as characters:

1. Created empty before parsing starts
2. Passed to each `AISectionParser.parse()` call via `scene_registry` kwarg
3. AI receives existing scenes in prompt (to reuse `scene_id`s)
4. AI returns a scene when the setting changes (or reuses the current one)
5. Scene upserted into registry; `scene_id` stamped on each segment
6. Updated registry passed to next section

Each segment carries a `scene_id` referencing its acoustic environment. The `SegmentContextResolver` looks up the scene's `voice_modifiers` (LLM-provided deltas) and applies them additively on top of emotion-based presets.

### Context Window for Speaker Resolution

Each section is parsed with access to up to 5 preceding sections from the same chapter (noise-only sections are excluded before the cap is applied). The AI uses this context to:

- Resolve pronouns ("he", "she", "they") to registry entries
- Infer speakers from conversational turn-taking
- Handle bare quotes with no attribution text

Context never crosses chapter boundaries. Window size is configurable (default: 5).

This feature eliminated most `character_id: null` dialogue segments from test data (e.g., Mr. Bennet's lines in Pride and Prejudice chapter 1).

## Design Decisions

### Why Dataclasses Instead of Pydantic?

The domain models use Python `@dataclass` with type annotations, not Pydantic. This keeps the domain layer lightweight and stdlib-only. Validation happens at parsing boundaries, not inside the domain.

Future work may introduce Pydantic for external API contracts (if TTS providers require strict validation).

### Why Character Registry Lives on Book?

The registry is a sibling output of the parsing pipeline, but it's stored as a field on `Book` (`Book.character_registry`) rather than returned as a separate tuple.

This decision was made to keep the registry co-located with the Book during the parsing pipeline. `Book.to_dict()` serialises the registry as a `"character_registry"` list (each entry uses `Character.to_dict()`). `Book.from_dict()` restores the full registry on deserialisation. The registry is always populated (at minimum with the narrator) and never null.

### Section Filtering

A `SectionFilter` in `parsers/section_filter.py` removes junk content before AI parsing:

- Page number artifacts (`{6}`, `{12}`) are dropped entirely
- Copyright blocks (`[Copyright ...]`) are dropped entirely
- Illustration captions are kept and tagged with `section_type='illustration'`

The filter is applied inside `StaticProjectGutenbergHTMLContentParser` after section extraction. Additionally, the AI parser classifies residual junk as `SegmentType.OTHER` as a fallback.

## Testing Strategy

### Unit Tests

- Live next to source files: `<module>_test.py` (Go-style)
- Cover all public methods on domain models, parsers, workflows
- Mock external dependencies (AI, downloader)

### Integration Tests

- Live in `tests/`
- Test real workflows end-to-end (with real AWS Bedrock calls, marked `@pytest.mark.integration`)
- Excluded from default test run via `-m "not integration"`

### Coverage Targets

- 100% on `domain/` (domain models are the contract)
- High coverage on `parsers/` and `workflows/` (business logic)
- Lower coverage acceptable on `ai/`, `downloader/`, `audio/` (thin adapters)

## Out of Scope (Current Implementation)

- Multi-narrator support (e.g., alternating POV chapters)
- EPUB or PDF input formats
- Character merging (detecting duplicate registry entries)
- Retroactive re-parsing (updating earlier sections after new context)

These features exist as user stories or deferred work in `docs/specs/`.
