# Workflows

End-to-end orchestration of the book-to-audiobook pipeline. Each workflow runs one stage (parse, AI-beatation, TTS, ambient, sfx, music, mix) by composing the underlying components and accepting either a URL or a cached `book_id`.

## Workflow

`run(request: WorkflowRequest) -> Book`

All concrete workflows share a single `run(request: WorkflowRequest)` signature. `WorkflowRequest` is a frozen dataclass that is derived from user request.

### create_workflow

Registry-based simple factory that maps a CLI workflow name to a builder callable returning a wired `Workflow`.

### AIWorkflow

Drives the `chapter_parser` prompt over the chapters in a `BookParseContext`. For each chapter still needing parsing, it builds a typed `PromptInput` (`book_title_announcement` is prepended only when `Chapter.is_first` is true), calls the injected `AIProvider`, parses the response via `PromptOutput.from_dict(...)`, merges characters into `book.character_registry`, replaces the chapter's sections with the extracted beats, and persists the book through `BookStore.save(book)` after every chapter.

When an `AIArtifactStore` is injected, the rendered prompt and raw LLM response are written to `books/{book_id}/ai/chapter_{NNN}/prompt.md` and `response.json` for every chapter call. See [Repository](../store/README.md).

### CharactersWorkflow

Provisions a voice on the configured TTS vendor for every character emitted by the AI workflow. Each character's resulting voice token is stamped onto the character and persisted with the book. Must run after `ai` and before `tts`.

### MixWorkflow

TBA

### MusicWorkflow

TBA

### SfxWorkflow

TBA

### TTSWorkflow

Synthesises every narratable beat using voices resolved through the configured `CharacterProvider`. Builds one `BeatContextResolver` per chapter, asks the resolver for each beat's `BeatContext` (same-character `previous_text` / `next_text` and a 3-deep window of the same voice's prior request IDs), passes that context into `provide`, and records the returned request ID back into the resolver so the next beat in the same voice picks up the chain. The chain resets at every chapter boundary.

