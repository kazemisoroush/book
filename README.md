# Audiobook Generator

A full-cast audiobook generator that converts text books into narrated audio with different voices for each character.

## Features

- **Character Recognition**: Automatically identifies dialogue and assigns unique voices to characters
- **Extensible TTS**: Interface-based design allows easy switching between TTS providers
  - ElevenLabs (high quality, paid)
  - Local TTS (piper/espeak, free)
- **SOLID Architecture**: Clean separation of concerns with dependency injection
- **TDD**: Comprehensive test coverage
- **Format Support**: Currently supports plain text books (extensible to other formats)

## Architecture

```
src/
├── domain/          # Core models (Book, Chapter, Segment)
├── parsers/         # Book parsers (text, future: PDF, EPUB)
├── tts/             # TTS provider implementations
├── voice_assignment.py  # Character-to-voice mapping
└── audio_generator.py   # Main orchestration
```

### Key Components

- **BookParser**: Interface for parsing different book formats
- **TTSProvider**: Interface for different TTS engines
- **VoiceAssigner**: Maps characters to voice IDs
- **AudioGenerator**: Orchestrates the conversion process

## Quick Start

### Run the example

```bash
python3 example.py
```

### Discover characters

```bash
python3 -m src.cli books/pg1342.txt --discover-characters
```

### Generate audiobook (local TTS)

```bash
python3 -m src.cli books/pg1342.txt --provider local
```

### Generate audiobook (ElevenLabs)

```bash
export ELEVENLABS_API_KEY=your_key_here
python3 -m src.cli books/pg1342.txt --provider elevenlabs --elevenlabs-api-key $ELEVENLABS_API_KEY
```

## Output

Audio files are organized by chapter:
```
output/
├── chapter_001/
│   ├── 0000_narration.wav
│   ├── 0001_dialogue_elizabeth.wav
│   ├── 0002_narration.wav
│   └── ...
├── chapter_002/
│   └── ...
```

## Testing

Tests are co-located with source files (Go-style):
```
src/
├── models.py
├── models_test.py         # Tests for models.py
├── audio_generator.py
└── audio_generator_test.py # Tests for audio_generator.py
```

Run all tests:
```bash
python3 -m pytest src/ -v
```

Run specific test file:
```bash
python3 -m pytest src/parsers/text_parser_test.py -v
```

## Extending

### Add a new TTS provider

1. Create a new class implementing `TTSProvider`
2. Implement `synthesize()` and `get_available_voices()`
3. Use it in the CLI or create your own script

### Add a new book format parser

1. Create a new class implementing `BookParser`
2. Implement `parse()` to return a `Book` object
3. Register it in the CLI

## Dependencies

- Python 3.10+
- pytest (testing)
- elevenlabs (optional, for ElevenLabs provider)
- piper-tts or espeak (optional, for local TTS)

## Known Issues & Immediate TODOs

### Current Dialogue Detection Issues

**Issue 1: Dialogue without Attribution**
- Problem: Back-and-forth conversations often drop attribution after speakers are established
- Example: `"What is his name?"` with no "said X" is treated as narration
- Impact: Many dialogue segments incorrectly classified as narration in output files

**Issue 2: Speaker Inconsistency**
- Problem: Same character identified by multiple descriptors (she/lady/wife/his wife)
- Example: Mrs. Bennet appears as `[lady]`, `[she]`, and `[wife]` in same chapter
- Impact: Same character gets multiple different voices, confusing for listeners

### Proposed Solution Architecture

#### 1. Character Registry System (PRIORITY)
**Approach: Hybrid (Heuristics + Local AI)**

**Critical Flow:**
The character registry MUST be built BEFORE TTS generation:
1. Scan entire book upfront
2. Build complete character registry with canonical names
3. Map all descriptors/pronouns to canonical IDs
4. THEN proceed with TTS generation

**Implementation:**
- Phase 1: Heuristic extraction (fast scan for explicit names like "said John")
- Phase 2: Local AI enrichment (Ollama/LLaMA to map pronouns/descriptors)
- Phase 3: Build cached registry for runtime lookups

**Example mapping:**
```
"his lady" → "Mrs. Bennet"
"she" (in context) → "Mrs. Bennet"
"his wife" → "Mrs. Bennet"
"lady" → "Mrs. Bennet"
"Elizabeth" → "Elizabeth Bennet"
"Lizzy" → "Elizabeth Bennet"
```

#### 2. Quote Detection Interface
```
QuoteDetector (ABC)
    ↓ implementation
HybridQuoteDetector
    ├─ Heuristic rules (fast path for clear cases)
    └─ AIProvider (fallback for ambiguous cases)
```

**Clear Cases (No AI):**
- Has attribution ("said John") → Dialogue
- Isolated quote in academic text → Narration
- Previously identified speaker continues → Dialogue (with state tracking)

**Ambiguous Cases (Use AI):**
- Consecutive quotes without attribution
- First quote after narration break
- Mixed quotes and narration

#### 3. AI Provider Interface
```python
class AIProvider(ABC):
    def classify_dialogue(paragraph, context) -> DialogueClassification
    def resolve_speaker(descriptor, context) -> canonical_character_name
```

Planned providers:
- Claude API
- OpenAI API
- LLaMA (local)
- Extensible for future providers

#### 4. Context Tracking
```python
class ParsingContext:
    recent_paragraphs    # Last 3-5 for context
    active_speakers      # Current conversation participants
    character_registry   # Canonical names mapping
    in_conversation      # Dialogue state
```

### Implementation Steps

1. **Character Registry (FIRST)** ✅ Decision: Hybrid (Heuristics + Local AI)
   - [ ] Setup Ollama/LLaMA locally for AI enrichment
   - [ ] Phase 1: Implement heuristic name extraction (scan entire book)
   - [ ] Phase 2: Implement AI enrichment for descriptor mapping
   - [ ] Phase 3: Build character registry cache system
   - [ ] Integrate into parsing pipeline (run BEFORE TTS)
   - [ ] Add CLI command to preview character registry

2. **Quote Detection Refactor**
   - [ ] Create `QuoteDetector` interface
   - [ ] Extract current logic into pattern-based implementation
   - [ ] Implement context tracking (active speakers, conversation state)
   - [ ] Add conversation state detection

3. **AI Integration**
   - [ ] Create `AIProvider` interface (supports multiple providers)
   - [ ] Implement Ollama/LLaMA provider (local, free)
   - [ ] Build `HybridQuoteDetector` with heuristics + AI fallback
   - [ ] Add optional Claude/OpenAI providers for comparison

4. **Testing & Validation**
   - [ ] Test on Pride & Prejudice (current book)
   - [ ] Verify character consistency (same character = same voice)
   - [ ] Validate dialogue detection accuracy
   - [ ] Regenerate output files with new system
   - [ ] Test on other classic literature books

5. **Voice Assignment by Character Age** (Future)
   - [ ] Extract character age/demographic info from book context
   - [ ] Categorize characters (child, young adult, adult, elderly)
   - [ ] Assign age-appropriate voices
   - [ ] Support voice gender matching

### Open Questions

- Character naming format? "Mrs. Bennet" vs "Mrs Bennet" vs "Bennet"?
- AI provider priority? Start with one or build multi-provider from start?
- Confidence threshold for AI classification?
- Performance: How often to call AI?

## Future Enhancements

- **Voice categorization by age** (in roadmap above - assign age-appropriate voices)
- Emotion detection for voice modulation (happy, sad, angry, etc.)
- Background sounds (ambient, sound effects)
- PDF/EPUB support
- Audio post-processing (normalization, EQ)
- Web interface for easier book management
- Parallel processing for faster generation
- Multiple book format support (Kindle, Google Books, etc.)
- Voice cloning for custom character voices
