# US-033 — Staged Pipeline Workflow

## Problem

The pipeline is fire-and-forget. The `tts` workflow bundles AI parsing, voice
assignment, and audio synthesis into one monolithic run. The operator cannot
iterate on one stage without re-running everything. Each stage has different
costs and iteration cycles ($150 AI parse vs $30-$300 TTS vs $1-$10
ambient/sfx/music).

## Proposed Solution

Replace the monolithic `tts` workflow with separate workflows — one per stage.
Each workflow is a first-class `--workflow` value, not a sub-flag.

```
python scripts/run_workflow.py --workflow ai      --url URL
python scripts/run_workflow.py --workflow tts     --url URL
python scripts/run_workflow.py --workflow ambient --url URL
python scripts/run_workflow.py --workflow sfx     --url URL
python scripts/run_workflow.py --workflow music   --url URL
python scripts/run_workflow.py --workflow mix     --url URL
```

All workflows read from and write back to a single `book.json` via the
repository layer.

| Workflow | Input | Output |
|---|---|---|
| `ai` | Book URL | `book.json` (beats, characters, scenes) |
| `tts` | `book.json` | Segment MP3s; writes beat durations + paths back |
| `ambient` | `book.json` (needs TTS timing) | Ambient MP3s; writes paths + time ranges back |
| `sfx` | `book.json` (needs TTS timing) | SFX MP3s; writes paths + positions back |
| `music` | `book.json` (needs TTS timing) | Music MP3s; writes paths + time ranges back |
| `mix` | `book.json` + all audio files | Final `chapter.mp3` files |

The old `tts` workflow (which ran everything end-to-end) is removed. Running
all stages sequentially is just calling each workflow in order.
