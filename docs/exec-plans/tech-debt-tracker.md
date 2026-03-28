# Tech Debt Tracker

This file tracks known technical debt and deferred work. Items are prioritized by impact and effort.

## High Priority

### 1. Structured Logging Implementation

**Status**: Design exists, not implemented

**Problem**: Code uses bare `print()` statements instead of `structlog`.

**Impact**: Logs are not machine-parseable. Difficult to filter, aggregate, or monitor in production.

**Effort**: Medium (need to add structlog dependency, replace all print statements, add logging config)

**Files affected**: All modules (primarily workflows, parsers, main.py)

### 2. Section Filtering (User Story 04 Completion)

**Status**: Partial implementation (SegmentType.OTHER exists)

**Problem**: Junk sections (page numbers, copyright notices) are still sent to the AI for classification. This wastes LLM calls and API costs.

**Impact**: Higher costs, slower parsing, no preservation of illustration metadata.

**Effort**: Medium (need to implement SectionFilter, wire into content parser, handle illustration captions)

**Files affected**: `src/parsers/` (new section_filter.py), `static_project_gutenberg_html_content_parser.py`

**Reference**: `userstories/04_JunkSectionFiltering.md`

### 3. Main.py CLI Doesn't Use Config.from_cli()

**Status**: Config.from_cli() exists but is unused

**Problem**: main.py has minimal argparse (URL + output only). Config.from_cli() supports many flags (--provider, --no-grouping, etc.) but they're inaccessible.

**Impact**: Users cannot configure AWS region, model ID, or other settings via CLI. Must use env vars.

**Effort**: Low (wire main.py to use Config.from_cli(), add help text)

**Files affected**: `main.py`

## Medium Priority

### 4. CharacterRegistry Merging

**Status**: Deferred (noted in user story 02)

**Problem**: The AI may create duplicate registry entries for the same character (e.g., "Harry" and "Harry Potter").

**Impact**: Multiple voice slots wasted. Inconsistent character attribution.

**Effort**: High (need fuzzy matching, human confirmation UI, retroactive segment updates)

**Reference**: `userstories/02_CharacterRegistry.md` (out of scope section)

### 5. Multiple Narrators

**Status**: Deferred (noted in DESIGN.md)

**Problem**: Books with alternating POV chapters (different narrators per chapter) are not supported. All narration uses the single "narrator" character.

**Impact**: Cannot handle multi-POV books correctly. Voice remains same across POV changes.

**Effort**: High (need narrator detection per section, registry changes, workflow changes)

### 6. Cross-Chapter Context Windows

**Status**: Deferred (noted in ExecPlan 03)

**Problem**: Context windows don't cross chapter boundaries. Speaker resolution fails if dialogue spans chapter break.

**Impact**: Some ambiguous speakers at chapter boundaries remain unresolved.

**Effort**: Low (remove chapter boundary check, pass wider context)

**Risk**: May confuse AI with too much context, or introduce wrong speakers from previous chapter.

## Low Priority

### 7. TTS Integration

**Status**: Stubs exist, not implemented

**Problem**: The TTS layer (`tts/`) has interface definitions but no working implementations.

**Impact**: Cannot generate actual audio files. Project stops at JSON output.

**Effort**: High (need ElevenLabs API integration, voice assignment algorithm, audio assembly)

**Files affected**: `src/tts/elevenlabs_provider.py`, new voice assignment module, new audio assembly module

### 8. EmphasisSpan Usage

**Status**: Data model exists, not used downstream

**Problem**: `EmphasisSpan` records inline emphasis (bold, italic) in sections, but no downstream code uses it.

**Impact**: Emphasis is parsed but discarded. No prosody control in TTS.

**Effort**: Medium (need TTS provider support for SSML or prosody tags)

**Depends on**: TTS integration (#7)

### 9. EPUB and PDF Support

**Status**: Not implemented

**Problem**: Only supports Project Gutenberg HTML. Many books are available as EPUB or PDF.

**Impact**: Cannot process non-Gutenberg books.

**Effort**: High (need EPUB parser, PDF text extraction, handle different structures)

**Files affected**: New parsers in `src/parsers/`, new downloaders if needed

### 10. Integration Test Coverage

**Status**: Some integration tests exist, coverage is low

**Problem**: Integration tests are marked `@pytest.mark.integration` and require AWS credentials. Coverage on real workflows is incomplete.

**Impact**: Real bugs may slip through unit tests.

**Effort**: Medium (add more integration test cases, possibly use moto for AWS mocking)

## Resolved

*None yet.*
