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

## Future Enhancements

- Background sounds (ambient, sound effects)
- Emotion detection for voice modulation
- PDF/EPUB support
- Audio post-processing (normalization, EQ)
- Web interface
- Parallel processing for faster generation
