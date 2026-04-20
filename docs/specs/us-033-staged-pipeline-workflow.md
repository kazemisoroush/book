# US-033 — Staged Pipeline Workflow

## Problem

The pipeline is fire-and-forget. The operator cannot run individual stages
independently — the TTS workflow always re-runs AI first, there's no way to
iterate on voice quality without re-parsing, and no way to tweak ambient/music
without re-synthesising speech. Each stage has different costs and iteration
cycles ($150 AI parse vs $0 voice assignment vs $30-$300 TTS vs $1-$10
ambient/sfx/music). Running everything end-to-end to iterate on one stage
wastes time and money.

## Proposed Solution

Split the pipeline into 6 independent stages. A single `book.json` serves as
the database — each stage reads from it and writes back its own fields via the
repository layer. No separate manifest files; one model, one file.

### Stages

1. **ai** — Input: book URL. Output: `book.json` (segments, characters, scenes).
2. **tts** — Input: `book.json`. Output: segment MP3s. Writes back: segment durations, file paths.
3. **ambient** — Input: `book.json` (needs TTS timing). Output: ambient MP3s. Writes back: ambient file paths, time ranges.
4. **sfx** — Input: `book.json` (needs TTS timing). Output: sfx MP3s. Writes back: sfx file paths, positions.
5. **music** — Input: `book.json` (needs TTS timing). Output: music MP3s. Writes back: music file paths, time ranges.
6. **mix** — Input: `book.json` + all audio files. Output: final `chapter.mp3` files.

### Repository as the persistence layer

The existing `BookRepository` interface gains stage-specific update methods:

- `save_book()` — stage 1 (already exists)
- `update_tts_data()` — stage 2 writes segment durations and paths
- `update_ambient_data()` — stage 3 writes ambient paths and time ranges
- `update_sfx_data()` — stage 4 writes sfx paths and positions
- `update_music_data()` — stage 5 writes music paths and time ranges

Each method reads the current `book.json`, updates only its own fields, writes
back. A stage never touches fields owned by another stage.

### CLI

```
python scripts/run_workflow.py --workflow tts --url URL --stage ai
python scripts/run_workflow.py --workflow tts --url URL --stage tts
python scripts/run_workflow.py --workflow tts --url URL --stage ambient
python scripts/run_workflow.py --workflow tts --url URL --stage sfx
python scripts/run_workflow.py --workflow tts --url URL --stage music
python scripts/run_workflow.py --workflow tts --url URL --stage mix
python scripts/run_workflow.py --workflow tts --url URL              # all stages
```

### Key rules

- One file: `book.json` is the single source of truth.
- Each stage owns its fields — never overwrites another stage's data.
- Stages 3, 4, 5 depend on TTS timing data but are independent of each other.
- Re-running a stage overwrites only its own fields (e.g. re-running TTS
  clears old durations/paths and writes new ones, but doesn't touch ambient).
- The mix stage is deterministic — same `book.json` + same audio files = same
  output.
