# Architecture

## Overview

The audiobook generator is built as a layered pipeline that transforms Project Gutenberg HTML books into structured, character-segmented data ready for multi-voice TTS synthesis.

## Layer Model

The codebase is organized into functional modules, not strict layers. Dependencies flow as follows:

```
config → domain → (ai, parsers, downloader, tts, workflows) → main.py
```

No `types/`, `adapters/`, `services/`, or `cli/` directories exist. The implementation uses a pragmatic module structure optimized for clarity and testability.

## Module Responsibilities

### config/

Configuration management. All options support both CLI arguments and environment variables.

- `config.py` - `Config` and `AWSConfig` dataclasses
- `Config.from_env()` - Load from environment variables
- `Config.from_cli()` - Load from CLI args with env var fallback (not currently used by main.py)

**Currently**: Only `AWSConfig` is actively used (for Bedrock credentials).

### domain/

Core data models representing books, chapters, sections, segments, and characters.

- `Book` - Top-level container (metadata + content + character_registry); has `to_dict()` / `from_dict()` for full round-trip serialisation including the registry
- `BookMetadata` - Bibliographic information
- `BookContent` - Chapters and sections
- `Chapter` - Numbered chapter with title and sections
- `Section` - A paragraph, optionally segmented
- `Segment` - A piece of narration or dialogue; carries `emotion: Optional[str]` (a freeform lowercase auditory tag, e.g. `"whispers"`, `"laughs harder"`) for TTS rendering
- `SegmentType` - Enum: NARRATION, DIALOGUE, ILLUSTRATION, COPYRIGHT, OTHER
- `Character` - A voice character (narrator or speaker); fields: `character_id`, `name`, `description`, `is_narrator`, `sex`, `age`; has `to_dict()` / `from_dict()` for serialisation
- `CharacterRegistry` - Registry of all characters in a book

**Key invariant**: Every segment has a `character_id`. Narration segments always use `"narrator"`. This ensures no null speaker bugs.

### ai/

AI provider abstraction for LLM calls.

- `AIProvider` (ABC) - `generate(prompt, max_tokens) -> str`
- `AWSBedrockProvider` - AWS Bedrock Claude implementation; accepts optional `token_tracker` kwarg
- `TokenTracker` - Tracks per-call and cumulative token usage and estimated cost across Bedrock calls
- `ModelPricingEntry` / `MODEL_PRICING` / `get_pricing()` - Static pricing table and lookup for cost estimation
- `CallRecord` - Immutable record of a single invocation (model ID, token counts, estimated cost)

**Used by**: `AISectionParser` to segment dialogue and identify speakers.

### parsers/

Parsers for extracting structured data from HTML and using AI to segment text.

- `BookMetadataParser` (ABC)
- `BookContentParser` (ABC)
- `BookSectionParser` (ABC)
- `StaticProjectGutenbergHTMLMetadataParser` - Extracts title, author, etc. from HTML
- `StaticProjectGutenbergHTMLContentParser` - Extracts chapters/sections from HTML
- `AISectionParser` - AI-powered dialogue segmentation, speaker identification, and character description formation

**AI Section Parser Flow**:

1. Receives a `Section`, current `CharacterRegistry`, and optional `context_window` (up to `context_window` preceding sections, default 5)
2. Builds a prompt including the registry (for speaker reuse and current descriptions) and context (for pronoun/speaker resolution)
3. Calls `AIProvider.generate()`
4. Parses JSON response into `Segment` list, new `Character` entries (including inferred `sex`, `age`, and `description`), and `character_description_updates` for existing characters
5. Upserts new characters into the registry; applies description updates to existing characters
6. Returns `(segments, updated_registry)`

**Context Window**: The parser receives preceding sections from the same chapter as read-only context (capped to `context_window`, default 5). The workflow passes all preceding sections; the parser caps the list internally. Noise-only sections (OTHER/ILLUSTRATION/COPYRIGHT) are filtered out before the cap is applied, so the window always contains up to 5 substantive sections. This allows the AI to resolve ambiguous speakers (e.g., "he replied") by following conversational turn-taking.

### downloader/

Downloads books from external sources.

- `BookDownloader` (ABC) - `parse(url) -> bool`
- `ProjectGutenbergHTMLBookDownloader` - Downloads zip files, extracts HTML

**Output**: Books are downloaded to `books/{book_id}/` directory.

### workflows/

End-to-end processing orchestration.

- `Workflow` (ABC) - `run(url: str, chapter_limit: int = 3) -> Book`
- `ProjectGutenbergWorkflow` - Static parsing only (no AI segmentation)
- `AIProjectGutenbergWorkflow` - Download + static parse + AI section segmentation
- `TTSProjectGutenbergWorkflow` - Full pipeline: download, AI-parse, voice assign, TTS synthesise

All three concrete workflows share the `run(url, chapter_limit=3)` signature.
`chapter_limit=0` means all chapters; the default of 3 prevents accidental
full-book API runs. `chapter_limit` is an invocation parameter, not a
constructor parameter.

**AI Workflow Steps**:

1. Download book zip
2. Find HTML file
3. Parse metadata
4. Parse content (chapters/sections)
5. For each section in each chapter (up to `chapter_limit`):
   - Pass all preceding sections to `AISectionParser` (parser caps to `context_window`, default 5)
   - Call `AISectionParser.parse(section, registry, context_window)`
   - Thread updated registry to next section
6. Return `Book` with `chapter_limit` chapters and populated `character_registry`

**TTS Workflow Steps**:

1. Run `AIProjectGutenbergWorkflow.run(url, chapter_limit)` to get the parsed `Book`
2. Assign ElevenLabs voices via `VoiceAssigner.assign(registry)`
3. Call `TTSOrchestrator.synthesize_chapter()` for every chapter in the book
4. Return the `Book` (audio files are a side-effect written to `output_dir`)

### tts/

TTS provider abstractions and synthesis orchestration.

- `TTSProvider` (ABC) — `synthesize(text, voice_id, output_path, emotion=None)` / `get_available_voices()`
- `ElevenLabsProvider` — v2 SDK implementation (`client.text_to_speech.convert`); uses `eleven_v3` model; validates emotion strings against `VERIFIED_EMOTION_TAGS` (warn-and-fallback for unknown tags); prepends inline audio tags for verified non-neutral emotions; lazy client init
- `LocalTTSProvider` — piper/espeak stub
- `VoiceEntry` — dataclass wrapping an ElevenLabs voice (`voice_id`, `name`, `labels`)
- `VoiceAssigner` — deterministic voice assignment for a `CharacterRegistry`; narrator first, others matched by `sex`/`age`
- `TTSOrchestrator` — synthesises all speakable segments in a chapter, interleaves silence clips between segments (duration varies by speaker boundary type), stitches them via ffmpeg, saves `book.json`

**Voice assignment algorithm**: The narrator always receives the first voice.  Non-narrator characters receive the highest-scoring unassigned voice (score = number of matching `sex`/`age` labels).  Ties broken by pool position; voices cycle when exhausted.

### main.py (root)

CLI entry point.

**Current interface**:

```bash
# Parse only — download, AI-segment, output JSON
python main.py <gutenberg_url> [-o output.json]

# Full TTS pipeline — download, AI-segment, assign voices, synthesise Chapter 1
python main.py <gutenberg_url> --tts
```

Without `--tts`: Creates a `ProjectGutenbergWorkflow`, runs it with `chapter_limit=0` (all chapters), and outputs JSON to stdout or a file.

With `--tts`: Creates an `AIProjectGutenbergWorkflow`, runs it with `chapter_limit=1`, fetches ElevenLabs voices, assigns them via `VoiceAssigner`, synthesises segments via `TTSOrchestrator`, and prints the path to `output/chapter_01.mp3`.  Requires `ELEVENLABS_API_KEY` environment variable; exits non-zero with a clear message if absent.

**Preferred entry point**: `scripts/run_workflow.py` is the recommended CLI for most uses:

```bash
# AI parse (default) on 3 chapters
python scripts/run_workflow.py --url <url> --output output.json --chapters 3 --workflow ai

# Static parse only
python scripts/run_workflow.py --url <url> --workflow parse --chapters 0

# Full TTS pipeline
python scripts/run_workflow.py --url <url> --workflow tts
```

**Note**: `main.py` does NOT use `Config.from_cli()`. It has a minimal argparse setup. The extensive `Config` class is only used for AWS credentials inside workflows.

## Data Flow

```
1. URL (e.g., https://www.gutenberg.org/cache/epub/1342/pg1342-h.zip)
   ↓
2. ProjectGutenbergHTMLBookDownloader
   → downloads zip
   → extracts to books/{book_id}/
   → returns success boolean
   ↓
3. Workflow reads HTML file
   ↓
4. StaticProjectGutenbergHTMLMetadataParser(html)
   → BookMetadata
   ↓
5. StaticProjectGutenbergHTMLContentParser(html)
   → BookContent (chapters/sections with text and emphasis spans)
   ↓
6. CharacterRegistry.with_default_narrator()
   → registry = [Character(character_id="narrator", name="Narrator", is_narrator=True)]
   ↓
7. For each chapter (up to chapter_limit):
     For each section in chapter:
       context_window = all preceding sections in chapter (parser caps to context_window, default 5)
       ↓
       AISectionParser.parse(section, registry, context_window)
         → builds prompt with registry + context
         → calls AIProvider.generate()
         → parses JSON response
         → returns (segments, updated_registry)
       ↓
       section.segments = segments
       registry = updated_registry
   ↓
8. Book(metadata, content, character_registry)
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

### Why No Section Filtering?

User story 04 proposed a `SectionFilter` to remove junk content (page numbers, copyright notices, illustration captions). The implementation took a different approach:

- `SegmentType.OTHER` was added for non-narratable content
- AI parser handles junk gracefully by classifying it as OTHER
- Full filtering (removing sections before AI parsing) is deferred

This was a pragmatic trade-off: let the AI classify junk rather than building deterministic filters for every edge case.

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
- Lower coverage acceptable on `ai/`, `downloader/`, `tts/` (thin adapters)

## Out of Scope (Current Implementation)

- TTS voice synthesis
- Audio file generation
- Multi-narrator support (e.g., alternating POV chapters)
- EPUB or PDF input formats
- Section filtering (removing junk content before AI parsing)
- Character merging (detecting duplicate registry entries)
- Retroactive re-parsing (updating earlier sections after new context)

These features exist as user stories or deferred work in `docs/product-specs/` and `docs/exec-plans/`.
