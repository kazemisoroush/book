# Domain Package
`src/domain/` contains all core data model classes. This should be one class per file if there is more than that should refactor.

1. Book: Top-level container encapsulates the book. Two round parse fills this model. Parser classes parse a book file into Book model that is their solely purpose.

2. BookMetadata: Contains bibliographic information

3. BookContent: Contains content

4. Chapter: one to many relationship with BookContent. Numbered chapter with title and sections.

5. Section: one to many relationship with Chapter. A distinct piece of writing in a book that could be a paragraph, quote, narration, table of content, image caption. Section always parsed and added to book deterministic. No AI parser changes Section.

6. Beat: one to many relationship with section. This is smallest piece that turnes into an audio with the same tone. Could be a speach or just a sound in general. The type determines how this should made audible. A Beat is the argument to audio Providers.

7. Character: one to many relationship with BookContent. A voice character. Each Beat could have an optional reference to Character. Characters are determined by the AI Parser. See Parser for more information.

8. Scene: One to many relationship with BookContent. Frozen value object describing an acoustic environment. AI Parser determines Scene that the conversation is happening in. See Parser for more information.

9. CharacterRegistry: One to one relationship with BookContent. Holds every Character discovered during parsing and guarantees stable IDs across the whole book. Bootstrapped with a default narrator so narration beats always resolve. Supports upsert, lookup, and serialization.

10. SceneRegistry: One to one relationship with BookContent. Holds every Scene detected by the AI Parser. Mirrors CharacterRegistry so scenes can be reused across sections and chapters rather than re-created each time the setting is mentioned.

11. AIPrompt: Frozen value object describing a structured prompt sent to an LLM. Splits the prompt into a static portion (reusable, cache-friendly instructions) and a dynamic portion (book context, character registry, scene registry, surrounding context, and the text to parse) so providers can cache the static half. The argument to AIProvider.
