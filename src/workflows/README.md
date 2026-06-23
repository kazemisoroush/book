# Workflows

End-to-end orchestration of the book-to-audiobook pipeline. Each workflow runs one stage (parse, AI-beatation, TTS, ambient, sfx, music, mix) by composing the underlying components and accepting either a URL or a cached book ID.

## Workflow

All concrete workflows share a single run method. The request is a frozen dataclass derived from the user request.

### create_workflow

Registry-based simple factory that maps a CLI workflow name to a builder callable returning a wired workflow.

### ParseWorkflow

Downloads and parses a book into chapters and sections without AI beatation. Saves the parsed book via repositories.

### AIWorkflow

Drives the chapter parser prompt over each chapter. Persists AI artifacts when an artifact store is injected.

### CharactersWorkflow

Provisions a voice on the configured TTS vendor for every character emitted by the AI workflow.

### MixWorkflow

TBA

### MusicWorkflow

TBA

### SfxWorkflow

TBA

### TTSWorkflow

Synthesises every narratable beat using voices resolved through the configured character provider.
