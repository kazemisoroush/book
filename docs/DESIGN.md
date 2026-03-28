# Design Philosophy

## Core Principles

This project follows a strict set of design principles enforced through code review, testing, and mechanical checks (ruff, mypy, pytest).

## 1. Test-Driven Development

**Every feature starts with a failing test.**

- Write the test first (red)
- Write minimum implementation to pass (green)
- Refactor while keeping tests green

**Unit test placement**: Tests live next to the source file, named `<module>_test.py` (Go-style). Integration tests live in `tests/`.

**Coverage enforcement**: 100% coverage required on `domain/` models. High coverage expected on `parsers/` and `workflows/`.

## 2. SOLID Principles

### Single Responsibility

Each class has one reason to change:

- `AISectionParser` - segments text using AI (not responsible for downloading, metadata parsing, or TTS)
- `ProjectGutenbergHTMLBookDownloader` - downloads books (not responsible for parsing)
- `CharacterRegistry` - manages character list (not responsible for voice assignment)

### Open/Closed

Extend behavior through composition, not modification:

- `Workflow` ABC - create new workflows without modifying existing ones
- `AIProvider` ABC - swap LLM backends without touching the parser
- `BookContentParser` ABC - support new input formats without changing the domain

### Liskov Substitution

All implementations of an ABC are interchangeable:

- `StaticProjectGutenbergHTMLContentParser` and any future `EPUBContentParser` both return `BookContent`
- `AWSBedrockProvider` and any future `OpenAIProvider` both implement `generate(prompt) -> str`

### Interface Segregation

Clients depend only on the methods they use:

- `BookSectionParser.parse()` is a single method - no bloated interface
- `AIProvider.generate()` is a single method - no LLM-specific config methods

### Dependency Inversion

High-level modules depend on abstractions, not concrete implementations:

- `AISectionParser` depends on `AIProvider` ABC, not `AWSBedrockProvider`
- `AIProjectGutenbergWorkflow` depends on `BookSectionParser` ABC, not `AISectionParser`
- Concrete dependencies are wired at composition root (factory methods like `Workflow.create()`)

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

**Note**: Structured logging is not yet fully implemented. This is a design target, not current state.

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
- ElevenLabs API key: `ELEVENLABS_API_KEY` (future)

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

**Solution**: Pass a sliding window of surrounding sections as context. The AI section parser receives the current section plus the 3 preceding sections from the same chapter. With this context, the AI can:

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
- **Voice assignment** - mapping characters to specific TTS voices or actors
- **Audio synthesis** - generating actual audio files (TTS layer exists as stubs)

Each of these is a well-defined future problem. The current design does not preclude them, but does not solve them either.

## Agent-Based Development

This project uses a multi-agent TDD workflow:

- **Orchestrator** - owns a task end-to-end, verifies against acceptance criteria
- **Test Agent** - writes failing tests only
- **Coder Agent** - writes minimum implementation to pass tests
- **Doc Updater** - fixes doc/code drift

See [AGENTS.md](../AGENTS.md) for the full workflow.

The human gate sits after the Orchestrator's Completion Report. No PR is opened until the human approves.

## Non-Negotiables (Mechanically Enforced)

1. All tests pass (`pytest -v`)
2. Zero lint errors (`ruff check src/`)
3. Zero type errors (`mypy src/`)
4. 100% coverage on `domain/` models
5. Unit tests live next to source (`<module>_test.py`)
6. No API keys in source (env vars only)

These are enforced by CI and local checks. Violations fail the build.
