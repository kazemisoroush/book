# Design Philosophy

## 1. Test-Driven Development

**Every feature starts with a failing test.** Red → Green → Refactor.

Unit tests live next to the source file (`<module>_test.py`). Integration tests live in `tests/`. 100% coverage required on `domain/`.

## 2. SOLID Principles

All ABCs (`AIProvider`, `BookContentParser`, `Workflow`, etc.) are designed for single responsibility and dependency inversion. High-level modules depend on abstractions, not concrete implementations. See [core-beliefs.md](design-docs/core-beliefs.md) for principles.

## 3. Typed Models at Boundaries

All data crossing module boundaries uses typed dataclasses:

- `Book`, `Chapter`, `Section`, `Segment` - domain models
- `BookMetadata` - bibliographic data
- `Character`, `CharacterRegistry` - voice registry
- `Config`, `AWSConfig` - configuration

**No raw dictionaries** in function signatures. Parse external data (HTML, JSON, env vars) into typed models at the boundary.

**Note**: The project currently uses `@dataclass` from the Python standard library, not Pydantic. This keeps the domain layer lightweight. Pydantic may be introduced later for external API contracts.

## 4. Structured Logging Only

Use `structlog` with structured key-value pairs. Never use bare `print()` or `logging.info(str(...))`.

```python
# Good
logger.info("section_parsed", section_id=section.id, segment_count=len(segments))

# Bad
print(f"Parsed section {section.id} with {len(segments)} segments")
```

Structured logging is implemented across all modules.  A shared `configure()` function in `src/logging_config.py` initialises structlog at startup.  Every module obtains its own logger via `structlog.get_logger(__name__)`.

## 5. Type Annotations Everywhere

All public functions have type annotations. Mypy runs in strict mode.

```python
def parse(self, section: Section, registry: CharacterRegistry) -> tuple[list[Segment], CharacterRegistry]:
    ...
```

## 6. No Secrets in Source

API keys, credentials, and tokens live in environment variables only. Never hardcode secrets.

- AWS credentials: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
- Bedrock model: `AWS_BEDROCK_MODEL_ID`
- ElevenLabs API key: `ELEVENLABS_API_KEY` (required for `--tts`)

Configuration is validated at startup via the `config` module. Missing required secrets cause immediate failure with clear error messages.

## 7. No Hidden State

Avoid global mutable state. Pass dependencies explicitly.

- `CharacterRegistry` is threaded through the parsing pipeline as an explicit parameter
- `AIProvider` is injected into `AISectionParser` constructor
- `Config` is loaded once and passed to components that need it

**Exception**: `config.get_config()` is a lazy global for convenience in tests. Production code should avoid it.

## 8. Determinism in Domain and Services

Domain models and business logic must be deterministic and testable:

- No `datetime.now()` - pass time as a parameter or use a `Clock` abstraction
- No unseeded `random.random()` - use deterministic algorithms or pass a seed
- No file I/O in domain models - parse file content first, then pass strings/bytes to domain

**Adapters** (downloader, parsers, AI) may have side effects. That's their job.

## Why CharacterRegistry?

The registry solves two problems:

### 1. Voice Consistency

**A character is a voice, not a person.**

Harry Potter at age 11 and Harry Potter at age 17 may be the same literary character, but they're different voices (and could be different voice actors in an audiobook). The registry tracks voices, not literary identity.

Every segment belongs to a character. The character maps 1-to-1 with a TTS voice slot. This ensures consistent voice rendering across the entire book.

### 2. No Null Narrators

Before the registry, narration segments had `speaker: null`, causing bugs downstream.

Now every segment has a `character_id`. Narration segments always use `"narrator"`. The narrator is a character like any other - it just happens to own narration segments instead of dialogue.

The registry is always bootstrapped with a default narrator entry via `CharacterRegistry.with_default_narrator()` before parsing begins.

## Context Window for Speaker Resolution

Many dialogue segments lack explicit speaker attribution:

```
"You want to tell me, and I have no objection to hearing it."
```

A human reader knows from context that this is Mr. Bennet replying to his wife. But an AI parsing this section in isolation cannot identify the speaker.

**Solution**: Pass a sliding window of surrounding sections as context. The AI section parser receives the current section plus up to 5 preceding sections from the same chapter (noise-only sections such as OTHER/ILLUSTRATION/COPYRIGHT are excluded before the cap is applied). With this context, the AI can:

- Follow conversational turn-taking
- Resolve pronouns ("he", "she", "they") to registry entries
- Infer speakers from narrative flow

Context windows never cross chapter boundaries. This is a pragmatic trade-off: chapters are natural break points, and cross-chapter context would complicate the implementation significantly.

This feature reduced `character_id: null` dialogue segments to near-zero in test data.

## SegmentType.OTHER for Non-Narratable Content

Books contain junk that should not be read aloud:

- Page numbers (`{6}`, `{12}`)
- Copyright notices (`[Copyright 1894 ...]`)
- Metadata markers

Rather than filtering these out before AI parsing (which would require complex heuristics), the AI classifies them as `SegmentType.OTHER`. Downstream TTS code can skip OTHER segments.

This is a pragmatic choice: leverage the AI's understanding of content rather than maintaining a fragile ruleset.

**Future work**: A `SectionFilter` may be introduced to remove obvious junk (page numbers, copyright blocks) before AI parsing, saving LLM calls. Illustration captions would be kept and tagged (for future use in alt-text generation or illustration indexes).

## Deferred Complexity

These features are deliberately out of scope (for now):

- **Multiple narrators** (e.g., alternating POV chapters) - would require narrator detection per section
- **Character merging** - detecting that "Harry" and "Harry Potter" are the same character
- **Retroactive re-parsing** - updating earlier sections after discovering new context
- **Spoiler detection** - avoiding character names that reveal plot twists
- **Multi-chapter TTS** - only Chapter 1 is synthesised; later chapters require additional orchestration

Each of these is a well-defined future problem. The current design does not preclude them, but does not solve them either.
