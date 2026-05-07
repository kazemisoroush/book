
### Parser

Parsers turn a raw string into domain objects. A parser could work deterministicly or use AIProviders for its parsing activity.

1. BookMetadataParser: Abstract base for extracting bibliographic metadata (title, author, language, etc.) from a raw book file. Deterministic, no AI.

- StaticProjectGutenbergHTMLMetadataParser: Concrete BookMetadataParser for Project Gutenberg HTML files.


2. BookContentParser: Abstract base for extracting Chapters and Sections from a raw book file. Deterministic, no AI.

- StaticProjectGutenbergHTMLContentParser: Concrete BookContentParser for Project Gutenberg HTML files. Extracts Chapters and Sections and applies SectionFilter to drop page-number artefacts and copyright blocks.


- BookSource: Abstract base that encapsulates the full download → parse → cache pipeline for a given book format. get_book(url) returns a fully parsed Book; get_book_for_beatation(url, start_chapter, end_chapter, reparse) returns a BookParseContext containing only the chapters that still need AI parsing.

- ProjectGutenbergBookSource: Concrete BookSource for Project Gutenberg. Composes a downloader, metadata parser, content parser, and optional repository into a single entry point.

- BookSectionParser: Abstract base for the AI round of parsing. Takes a Section and returns the Beats it contains along with any newly discovered Characters and the current Scene.

- AISectionParser: Concrete BookSectionParser. Uses an AIProvider to split a Section into Beats, identify speakers against the CharacterRegistry, infer Character descriptions, and detect the current Scene. Also receives a rolling context window of preceding sections so the AI can resolve pronouns and bare quotes.

- SectionFilter: Deterministic filter applied during static content parsing. Drops junk sections (page numbers, copyright blocks) and tags illustration captions so they survive into the AI round with the right section_type.

- text_sanitizer: Pure function sanitize_beat_text(text) that strips trailing non-terminal punctuation (commas, semicolons, em-dashes) and normalizes whitespace. Called at Beat creation time as a safety net against TTS artefacts.

**AI Section Parser Flow**:

1. Receives a `Section`, current `CharacterRegistry`, and optional `context_window` (up to `context_window` preceding sections, default 5)
2. Builds a prompt including the registry (for speaker reuse and current descriptions) and context (for pronoun/speaker resolution); prompt includes instruction to strip trailing non-terminal punctuation from beat text
3. Calls `AIProvider.generate()`
4. Parses JSON response into `Beat` list, new `Character` entries (including inferred `sex`, `age`, and `description`), `character_description_updates` for existing characters, and an optional `Scene` (environment, acoustic hints, voice modifiers)
5. Applies `sanitize_beat_text()` to each beat's text field as a safety net (strips trailing commas, semicolons, em-dashes, etc.)
6. Filters out non-narratable beats (`beat_type` not in {NARRATION, DIALOGUE}) so cached output contains only speakable content
7. Upserts new characters into the character registry; upserts detected scene into the scene registry; stamps `scene_id` on each beat
8. Returns `(beats, updated_character_registry)`

**Context Window**: The parser receives preceding sections from the same chapter as read-only context (capped to `context_window`, default 5). The workflow passes all preceding sections; the parser caps the list internally. Noise-only sections (OTHER/ILLUSTRATION/COPYRIGHT) are filtered out before the cap is applied, so the window always contains up to 5 substantive sections. This allows the AI to resolve ambiguous speakers (e.g., "he replied") by following conversational turn-taking.
