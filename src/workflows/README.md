# Workflows

End-to-end orchestration of the book-to-audiobook pipeline. Each workflow runs one stage (parse, AI-beatation, TTS, ambient, sfx, music, mix) by composing the underlying components and accepting either a URL or a cached `book_id`.

## Workflow

All concrete workflows share a single `run(request: WorkflowRequest)` signature. `WorkflowRequest` is a frozen dataclass derived from the user request.

### create_workflow

Registry-based simple factory that maps a CLI workflow name to a builder callable returning a wired `Workflow`.

### AIWorkflow

Drives the `chapter_parser` prompt over each chapter in a `BookParseContext`. Persists AI artifacts through `ArtifactStore` when injected.

### CharactersWorkflow

Provisions a voice on the configured TTS vendor for every character emitted by the AI workflow.

### MixWorkflow

TBA

### MusicWorkflow

TBA

### SfxWorkflow

TBA

### TTSWorkflow

Synthesises every narratable beat using voices resolved through the configured `CharacterProvider`.
