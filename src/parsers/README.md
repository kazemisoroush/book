# Parsers

Parsers turn a raw string into domain objects. A parser could work deterministicly or use AIProviders for its parsing activity.

## BookMetadataParser

Abstract base for extracting bibliographic metadata (title, author, language, etc.) from a raw book file. Deterministic, no AI.

### StaticProjectGutenbergHTMLMetadataParser

Concrete BookMetadataParser for Project Gutenberg HTML files.

## BookContentParser

Abstract base for extracting Chapters and Sections from a raw book file. Deterministic, no AI.

### StaticProjectGutenbergHTMLContentParser

Concrete BookContentParser for Project Gutenberg HTML files. Extracts Chapters and Sections and applies SectionFilter to drop page-number artefacts and copyright blocks.

## BookSource

Abstract base that encapsulates the full download → parse → cache pipeline for a given book format. `get_book(url, start_chapter, end_chapter, refresh)` returns a `BookParseContext` containing the book (with cached chapters and registries if available), the list of chapters that still need AI parsing, and the full parsed content.

### ProjectGutenbergBookSource

Concrete BookSource for Project Gutenberg. Composes a downloader, metadata parser, content parser, and optional store into a single entry point.

The AI round of parsing now happens at the chapter level via `AIWorkflow` + the `chapter_parser` prompt; there is no longer a per-section parser class in this package.

## SectionFilter

Deterministic filter applied during static content parsing. Drops junk sections (page numbers, copyright blocks) and tags illustration captions so they survive into the AI round with the right section_type.

## text_sanitizer

Pure function sanitize_beat_text(text) that strips trailing non-terminal punctuation (commas, semicolons, em-dashes) and normalizes whitespace. Called at Beat creation time as a safety net against TTS artefacts.
