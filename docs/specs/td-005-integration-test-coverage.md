# TD-005 — Integration Test Coverage

**Priority**: Medium
**Effort**: Medium
**Status**: Open

## Problem

Integration tests are marked `@pytest.mark.integration` and require
live AWS Bedrock credentials to run. They are excluded from the default
`pytest` run and CI. Coverage on real workflow paths is essentially
zero in automated checks.

## Impact

- Real bugs in the AI parse or TTS pipeline only surface manually via
  `make verify`
- Regressions in the Bedrock prompt or response parsing are invisible
  until a human runs the smoke test

## What needs doing

- Add `moto` (AWS mock library) or a local stub for Bedrock calls so
  integration tests can run without real credentials
- Alternatively, record/replay real Bedrock responses with `pytest-recording`
  (VCR-style) so integration tests run offline
- Increase coverage on `src/workflows/` and `src/parsers/ai_section_parser.py`
  with at least one full chapter parse test that does not hit the real API

## Files affected

`tests/` (new integration test files), `pyproject.toml` (new test deps)
