# Audiobook Generator

A Python CLI that converts Project Gutenberg books into structured, multi-voice audiobook data with AI-powered dialogue segmentation and character tracking.

## What It Does

1. Downloads Project Gutenberg HTML books from a URL
2. Parses metadata (title, author, release date)
3. Extracts chapters and sections
4. Uses AI (AWS Bedrock Claude) to:
   - Segment text into dialogue and narration
   - Identify speakers and build a character registry
   - Handle complex cases like interrupted dialogue and cross-section context
5. Outputs a structured JSON representation with character-to-voice mappings

## Current State

**Parser Layer**: Complete. The system can download, parse, and AI-segment books.

**TTS Integration**: Complete. Multi-voice synthesis via ElevenLabs with emotion-aware delivery, ambient background sound, cinematic sound effects, and per-scene voice modifiers.

## Quick Start

### Prerequisites

- Python 3.10+
- AWS credentials with Bedrock access (for AI section parsing)
- Project dependencies installed (see `pyproject.toml`)

### Installation

```bash
# Install in development mode
pip install -e ".[dev]"
```

### Usage

```bash
# Parse a Project Gutenberg book
python main.py "https://www.gutenberg.org/files/1342/1342-h.zip"

# Save output to file
python main.py "https://www.gutenberg.org/files/1342/1342-h.zip" -o output.json
```

### Environment Variables

The AI parser requires AWS credentials:

```bash
export AWS_REGION=us-east-1
export AWS_BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-20250514-v1:0
# Optional: AWS credentials (or use default credential chain)
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
```

## Development

### Run Tests

```bash
# All tests
pytest -v

# Exclude integration tests
pytest -v -m "not integration"
```

### Lint and Type Check

```bash
# Lint
ruff check src/

# Type check
mypy src/
```

### Test Coverage

```bash
# Run with coverage report
pytest --cov=src --cov-report=term-missing
```

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for the technical architecture overview.

See [AGENTS.md](AGENTS.md) for the agent-based development workflow.

## Documentation

| Topic | Location |
|---|---|
| Architecture overview | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Design philosophy | [docs/DESIGN.md](docs/DESIGN.md) |
| Agent workflow | [AGENTS.md](AGENTS.md) |
| Agent instructions | [CLAUDE.md](CLAUDE.md) |
| Specs (active & completed) | [docs/specs/](docs/specs/) |

## Project Structure

```
src/
  config/          Configuration management
  domain/          Core data models (Book, Chapter, Segment, CharacterRegistry)
  ai/              AI provider abstractions (AWS Bedrock)
  parsers/         HTML and AI section parsing
  downloader/      Book downloading (Project Gutenberg)
  tts/             TTS synthesis (ElevenLabs), voice assignment, audio assembly
  workflows/       End-to-end processing orchestration
main.py            CLI entry point
```

## Output Format

The parser produces JSON with this structure:

```json
{
  "metadata": {
    "title": "Pride and Prejudice",
    "author": "Jane Austen",
    "releaseDate": "1998-06-01",
    "language": "English"
  },
  "content": {
    "chapters": [
      {
        "number": 1,
        "title": "Chapter 1",
        "sections": [
          {
            "text": "...",
            "segments": [
              {
                "text": "My dear Mr. Bennet",
                "segment_type": "dialogue",
                "character_id": "mrs_bennet"
              },
              {
                "text": "said his lady to him one day,",
                "segment_type": "narration",
                "character_id": "narrator"
              }
            ]
          }
        ]
      }
    ]
  },
  "character_registry": {
    "characters": [
      {
        "character_id": "narrator",
        "name": "Narrator",
        "description": null,
        "is_narrator": true
      },
      {
        "character_id": "mrs_bennet",
        "name": "Mrs. Bennet",
        "description": null,
        "is_narrator": false
      }
    ]
  }
}
```

## Contributing

This project follows TDD and SOLID principles. All implementation work is done through the agent workflow described in [AGENTS.md](AGENTS.md).

## License

This project is for educational and research purposes. Project Gutenberg content is in the public domain in the United States.
