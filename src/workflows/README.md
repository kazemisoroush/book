# Workflows

End-to-end orchestration of the book-to-audiobook pipeline. Each workflow runs one stage (parse, AI-beatation, TTS, ambient, sfx, music, mix) by composing the underlying components and accepting either a URL or a cached `book_id`.

## Workflow

`run(request: WorkflowRequest) -> Book`

All concrete workflows share a single `run(request: WorkflowRequest)` signature. `WorkflowRequest` is a frozen dataclass that is derived from user request.

### create_workflow

Registry-based simple factory that maps a CLI workflow name to a builder callable returning a wired `Workflow`.

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

TBA

## MoodTracker

TBA
