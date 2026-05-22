# Workflows

End-to-end orchestration of the book-to-audiobook pipeline. Each workflow runs one stage (parse, AI-beatation, TTS, ambient, sfx, music, mix) by composing the underlying components and accepting either a URL or a cached `book_id`.

## Workflow

`run(request: WorkflowRequest) -> Book`

All concrete workflows share a single `run(request: WorkflowRequest)` signature. `WorkflowRequest` is a frozen dataclass that is derived from user request.

### create_workflow

Registry-based simple factory that maps a CLI workflow name to a builder callable returning a wired `Workflow`.

### AIProjectGutenbergWorkflow

AI section beatation workflow; takes a `BookSource` (encapsulates download + parse + cache) and a `BookSectionParser` (for AI beatation).

**Steps**:

1. Call `BookSource.get_book_for_beatation(url, start_chapter, end_chapter, reparse)` to obtain a `BookParseContext` (contains: `book` with registries, `chapters_to_parse`, and `content`)
2. For each chapter in `chapters_to_parse`:
   For each section in chapter:
   - Pass all preceding sections to `AISectionParser` (parser caps to `context_window`, default 5)
   - Call `AISectionParser.parse(section, registry, context_window, scene_registry=scene_registry)`
   - Thread updated character and scene registries to next section
   - After each chapter: flush to repository via `BookSource` (if one was provided)
3. Return `Book` with chapters from `start_chapter` to `end_chapter`, populated `character_registry`, and `scene_registry`

### AmbientWorkflow

TBA

### MixWorkflow

TBA

### MusicWorkflow

TBA

### SfxWorkflow

TBA

### TTSWorkflow

Full pipeline: download, AI-parse, voice assign, TTS synthesise.

**Steps**:

1. Run `AIProjectGutenbergWorkflow.run(WorkflowRequest(url, start_chapter, end_chapter, ...))` to get the parsed `Book`
2. Assign ElevenLabs voices via `VoiceAssigner.assign(registry)`
3. Call `AudioOrchestrator.synthesize_chapter()` for every chapter in the book
4. Return the `Book` (audio files are a side-effect written to `{books_dir}/{book_id}/audio/`)

## MoodTracker

TBA
