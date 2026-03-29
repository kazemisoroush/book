# TD-002 — CLI Config Not Wired

**Priority**: Medium
**Effort**: Low
**Status**: Open

## Problem

`Config.from_cli()` exists and supports many flags (`--provider`,
`--no-grouping`, `--crossfade`, `--discover-characters`, etc.) but
`main.py` uses a minimal handwritten `argparse` setup and never calls
it. All those flags are inaccessible to users; they must fall back to
environment variables.

`scripts/run_workflow.py` (added in US-008) also has its own minimal
argparse instead of delegating to `Config`.

## Impact

- Users cannot configure AWS region, Bedrock model ID, or ElevenLabs
  settings via CLI flags
- `Config.from_cli()` is tested but dead code from an end-user
  perspective
- Two diverging CLI surfaces (`main.py` and `scripts/run_workflow.py`)

## What needs doing

- Wire `main.py` to call `Config.from_cli()` and pass the result into
  workflows instead of reading individual env vars
- Decide whether `scripts/run_workflow.py` should absorb `main.py` or
  stay separate; eliminate the duplication

## Files affected

`main.py`, `scripts/run_workflow.py`
