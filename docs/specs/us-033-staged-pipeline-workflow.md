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

Split the pipeline into 6 independent stages. Each stage reads its inputs from
disk and writes its outputs to disk. Stages can be run individually via
`--stage` flag or sequentially (default).

### Stages

1. **ai** — Input: book URL. Output: `book.json` (namespaced per AI model).
2. **tts** — Input: `book.json`. Output: segment MP3s + `tts_manifest.json`.
3. **ambient** — Input: `book.json` + `tts_manifest.json` (for timing). Output: ambient MP3s + `ambient_manifest.json`.
4. **sfx** — Input: `book.json` + `tts_manifest.json`. Output: sfx MP3s + `sfx_manifest.json`.
5. **music** — Input: `book.json` + `tts_manifest.json`. Output: music MP3s + `music_manifest.json`.
6. **mix** — Input: `book.json` + all manifests + all audio files. Output: final `chapter.mp3` files.

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

### File layout

```
books/{id}/
  book.json                  # Stage 1 — immutable AI creative output
  tts_manifest.json          # Stage 2 — segment paths + durations per chapter
  ambient_manifest.json      # Stage 3 — ambient file paths + time ranges
  sfx_manifest.json          # Stage 4 — sfx file paths + positions
  music_manifest.json        # Stage 5 — music file paths + time ranges
  audio/{chapter}/
    segments/{provider}/     # TTS segment MP3s
    ambient/{provider}/      # Ambient MP3s
    sfx/{provider}/          # SFX MP3s
    music/{provider}/        # Music MP3s
    chapter.mp3              # Stage 6 — final mixed output
```

### Key rules

- `book.json` is immutable after stage 1. Downstream stages never modify it.
- Each manifest is owned by exactly one stage. Re-running a stage overwrites
  only its manifest.
- The mix stage validates that all manifests are consistent (same segment
  counts, same chapters) before proceeding. Fails loud on mismatch.
- Stages 3, 4, 5 (ambient/sfx/music) depend on `tts_manifest.json` for timing
  information but are independent of each other — they can run in parallel.
- AI model namespacing: `book.json` path includes the model identifier so
  different models don't overwrite each other's parse results.
