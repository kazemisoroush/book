# Domain

`src/domain/` contains all core data model classes. This should be one class per file if there is more than that should refactor.

## Book

Top-level container encapsulates the book. Two round parse fills this model. Parser classes parse a book file into Book model that is their solely purpose.

## BookMetadata

Contains bibliographic information

## BookContent

Contains content

## BookParseContext

TBA

## Chapter

one to many relationship with BookContent. Numbered chapter with title and sections.

## Section

one to many relationship with Chapter. A distinct piece of writing in a book that could be a paragraph, quote, narration, table of content, image caption. Section always parsed and added to book deterministic. No AI parser changes Section.

## SectionRef

TBA

## Beat

one to many relationship with section. This is smallest piece that turnes into an audio with the same tone. Could be a speach or just a sound in general. The type determines how this should made audible. A Beat is the argument to audio Providers.

## BeatType

Enum that classifies a Beat by its rendering role. Determines which provider handles the beat during audio synthesis, or whether the beat is preserved in the data model but skipped. Specific values are defined in [beat.py](beat.py).

## Character

one to many relationship with BookContent. A voice character. Each Beat could have an optional reference to Character. Characters are determined by the AI Parser. See Parser for more information.

## CharacterRegistry

One to one relationship with BookContent. Holds every Character discovered during parsing and guarantees stable IDs across the whole book. The default narrator is built via [make_default_narrator](character.py) and seeded by the caller. Supports upsert, lookup, and serialization.

## Scene

One to many relationship with BookContent. Frozen value object describing an acoustic environment. AI Parser determines Scene that the conversation is happening in. See Parser for more information.

## SceneRegistry

One to one relationship with BookContent. Holds every Scene detected by the AI Parser. Mirrors CharacterRegistry so scenes can be reused across sections and chapters rather than re-created each time the setting is mentioned.

