# Repository

Persistence layer for caching fully-parsed ``Book`` models and the
intermediate artifacts each pipeline stage produces.

## BookRepository

`save(book)` / `load(book_id)` / `exists(book_id)` plus `save_input(book)` / `load_input(book_id)` for the pre-AI snapshot. Abstract so the storage backend can be swapped (filesystem today, database later) without changing callers. `save()` derives the id from `Book.book_id`; `load()` / `exists()` take a `book_id` directly so callers can probe the cache before having a `Book`.

### FileBookRepository

File-based implementation that writes two JSON files per book under `{base_dir}/{book_id}/`:

* `metadata.json` is the pre-AI snapshot saved by `save_input(book)`. Contains the parsed metadata and deterministic chapters and sections before any LLM call.
* `book.json` is the final snapshot saved by `save(book)` after the AI workflow has merged beats and characters. Loaded back via `load(book_id)`.

`base_dir` defaults to `./books/`.

## api_request_recorder

`write_api_request(request_path, method, url, headers, body)` writes one outbound API call to disk as a JSON artifact. Captures the method, URL, redacted headers, body, and a copy-pasteable `curl` command. Used by both TTS providers ([elevenlabs](../audio/tts/elevenlabs_tts_provider.py), [fish_audio](../audio/tts/fish_audio_tts_provider.py)) and the [ElevenLabs character provider](../characters/elevenlabs_character_provider.py) so every external call has an inspectable record on disk.

## AIArtifactStore

`save_prompt(book_id, chapter_number, prompt)` / `save_response(book_id, chapter_number, response)` for capturing the per-chapter LLM input and raw output during `AIWorkflow.run`.

### FileAIArtifactStore

File-based implementation that writes under `{base_dir}/{book_id}/ai/chapter_{NNN}/`:

* `prompt.md` is the rendered prompt string passed to the LLM.
* `response.json` is the raw JSON response, pretty-printed when valid.

## book_id

`Book.book_id` (and `BookMetadata.book_id`) is a `@property` that derives a stable, human-readable directory name from `{title}:{author}` with filesystem-unsafe characters replaced. Used by `AIWorkflow` to skip redundant AI calls on repeat runs.
