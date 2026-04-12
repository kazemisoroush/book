# US-008 — Unified Workflow Interface with TTS

## Goal

Consolidate all book-processing entry points into a coherent set of three
workflows. Remove `scripts/parse_book.py`. Introduce a new full-pipeline
workflow that adds ElevenLabs TTS to the existing AI parse. Update the
`Workflow` base interface so all workflows share a consistent `run(url,
chapter_limit)` signature.

---

## Background / motivation

Currently the codebase has two entry paths for the same AI parse pipeline:

- `AIProjectGutenbergWorkflow.run(input)` — accepts a URL via the base
  `Workflow.run()` signature, chapter limiting done via the constructor
- `scripts/parse_book.py` — accepts a local book ID, hardcodes paths, and
  re-implements the parse loop itself

This duplication means workflow logic drifts, the script cannot be unit-tested,
and callers have to know two different invocation styles. There is also no
workflow that drives the full pipeline through ElevenLabs TTS.

---

## Acceptance criteria

1. `Workflow.run(url: str, chapter_limit: int = 3) -> Book` — the
   base abstract method has this exact signature. `input: str` is gone.
   Default of `3` is intentional: it prevents accidental full-book AI/TTS runs
   that incur large API costs. Callers must pass `chapter_limit=0` explicitly
   to mean "all chapters".

2. `ProjectGutenbergWorkflow.run(url, chapter_limit=3)` — downloads and parses
   the book; returns only the first `chapter_limit` chapters (`0` = all).

3. `AIProjectGutenbergWorkflow.run(url, chapter_limit=3)` — downloads, parses,
   and AI-segments the book. `chapter_limit` limits both segmentation and the
   chapters in the returned `Book` (`0` = all). `chapter_limit` is removed from
   the constructor and from `create()`.

4. `TTSProjectGutenbergWorkflow` exists in
   `src/workflows/tts_project_gutenberg_workflow.py` and:
   - Accepts `output_dir: Path` in its constructor (where audio files are written)
   - Has a `create(output_dir: Path) -> TTSProjectGutenbergWorkflow` factory that
     wires all default dependencies (downloader, parsers, AI provider, ElevenLabs
     TTS provider, voice assigner)
   - `run(url, chapter_limit=3)` executes the full pipeline:
     1. Download + static parse (reusing parse logic, not duplicating it)
     2. AI section segmentation (up to `chapter_limit` chapters)
     3. Voice assignment via `VoiceAssigner`
     4. TTS synthesis via `AudioOrchestrator` for every chapter in scope
   - Returns the `Book` produced by the AI parse (audio files are a side effect
     written to `output_dir`)

5. `scripts/parse_book.py` is deleted.

6. `Makefile` targets `parse` and `verify` are updated to invoke
   `AIProjectGutenbergWorkflow` directly via a new minimal script
   `scripts/run_workflow.py` (or inline Python), so there is no duplication of
   pipeline logic in scripts. The new entry point accepts:
   - `--url` — Project Gutenberg zip URL (required)
   - `--output` — output JSON path (default: `output.json`)
   - `--chapters` — chapter limit (default: `3`; pass `0` for all)
   - `--workflow` — `parse` | `ai` | `tts` (default: `ai`)

7. All existing tests pass. New unit tests cover:
   - `ProjectGutenbergWorkflow.run()` with a chapter_limit slices chapters
   - `AIProjectGutenbergWorkflow.run()` no longer accepts chapter_limit in
     `__init__` / `create()`
   - `TTSProjectGutenbergWorkflow.run()` wires AI parse → voice assign → TTS
     (one mock for the AI workflow, one mock for AudioOrchestrator — tested at
     the integration seam only)

8. `make verify` still runs end-to-end on 3 chapters and produces `output.json`.

---

## Out of scope

- Changing parser logic (metadata or content parsers)
- Changing the AI provider (`AWSBedrockProvider`) or section-parser prompt logic
- TTS provider interface or implementation changes are **in scope** where needed
  to make `TTSProjectGutenbergWorkflow` work cleanly — fix whatever is awkward,
  don't work around it
- Supporting non-Project-Gutenberg input sources
- Multi-chapter audio stitching across chapters (each chapter remains a
  separate MP3; that is `AudioOrchestrator`'s existing behaviour)
- Progress reporting / streaming output to the terminal during TTS

---

## Key design decisions

### chapter_limit in run(), not __init__()
The chapter limit is an invocation parameter, not a configuration parameter.
Moving it to `run()` means a single workflow instance can be reused for
different invocations without reconstruction.

### Default chapter_limit = 3
API calls to both Bedrock and ElevenLabs cost real money. A default of `3`
makes accidental full-book runs impossible — the caller must opt in explicitly
with `chapter_limit=0` (all chapters). Every workflow and the CLI shim share
this default.

### TTS provider changes are in scope
If the existing `TTSProvider` / `ElevenLabsProvider` interface makes it awkward
to wire `TTSProjectGutenbergWorkflow`, fix the provider. The goal is a clean
workflow, not preservation of every existing TTS interface detail.

### TTSProjectGutenbergWorkflow returns Book
Audio is a side effect. Keeping the return type consistent with the rest of the
`Workflow` hierarchy means the TTS workflow can be swapped in anywhere a
`Workflow` is expected and callers can still inspect the structured `Book` data.

### scripts/parse_book.py deleted, not refactored
The script duplicates `AIProjectGutenbergWorkflow` logic. The correct fix is
deletion, not a thin wrapper — the workflow itself is the entry point. The new
`scripts/run_workflow.py` is a pure dispatch shim (< 40 lines) with no logic.

---

## Files changed (expected)

| File | Change |
|---|---|
| `src/workflows/workflow.py` | Update abstract `run()` signature |
| `src/workflows/project_gutenberg_workflow.py` | Implement new `run()` signature |
| `src/workflows/ai_project_gutenberg_workflow.py` | Move `chapter_limit` from `__init__` to `run()` |
| `src/workflows/tts_project_gutenberg_workflow.py` | New file |
| `src/workflows/__init__.py` | Export new workflow |
| `scripts/parse_book.py` | Deleted |
| `scripts/run_workflow.py` | New dispatch shim |
| `Makefile` | Update `parse` and `verify` targets |
| New test files alongside changed modules | TDD — tests written first |
