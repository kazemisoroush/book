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
- Build canonical character list with full names (e.g., "Mrs. Bennet", "Elizabeth Bennet")
- Map descriptors/pronouns to canonical IDs
- Ensure consistent character names throughout entire book
- **Question:** Does this require AI (e.g., LLaMA) or can we use heuristics?

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

1. **Character Registry (FIRST)**
   - [ ] Decide: AI-based or heuristic approach for character extraction
   - [ ] Build full character list with canonical names
   - [ ] Create character-to-descriptor mapping
   - [ ] Inject into parsing pipeline

2. **Quote Detection Refactor**
   - [ ] Create `QuoteDetector` interface
   - [ ] Extract current logic into pattern-based implementation
   - [ ] Implement context tracking

3. **AI Integration**
   - [ ] Create `AIProvider` interface
   - [ ] Implement first provider (Claude/OpenAI/LLaMA - TBD)
   - [ ] Build `HybridQuoteDetector` with heuristics + AI fallback

4. **Testing & Validation**
   - [ ] Test on Pride & Prejudice (current book)
   - [ ] Verify character consistency
   - [ ] Validate dialogue detection accuracy
   - [ ] Regenerate output files

### Open Questions

- Character naming format? "Mrs. Bennet" vs "Mrs Bennet" vs "Bennet"?
- AI provider priority? Start with one or build multi-provider from start?
- Confidence threshold for AI classification?
- Performance: How often to call AI?

## Future Enhancements

- Background sounds (ambient, sound effects)
- Emotion detection for voice modulation
- PDF/EPUB support
- Audio post-processing (normalization, EQ)
- Web interface
- Parallel processing for faster generation
