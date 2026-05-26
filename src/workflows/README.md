# Workflows

End-to-end orchestration of the book-to-audiobook pipeline. Each workflow runs one stage (parse, AI-beatation, TTS, ambient, sfx, music, mix) by composing the underlying components and accepting either a URL or a cached `book_id`.

## Workflow

`run(request: WorkflowRequest) -> Book`

All concrete workflows share a single `run(request: WorkflowRequest)` signature. `WorkflowRequest` is a frozen dataclass that is derived from user request.

### create_workflow

Registry-based simple factory that maps a CLI workflow name to a builder callable returning a wired `Workflow`.

### AmbientWorkflow

TBA

### CharactersWorkflow

Provisions a voice on the configured TTS vendor for every character emitted by the AI workflow. Each character's resulting voice token is stamped onto the character and persisted with the book. Must run after `ai` and before `tts`.

### MixWorkflow

TBA

### MusicWorkflow

TBA

### SfxWorkflow

TBA

### TTSWorkflow

Synthesises every narratable beat using voices resolved through the configured `CharacterProvider`.

TBA

