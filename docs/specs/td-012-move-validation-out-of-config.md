# TD-012 — Move Validation Out of Config

## Goal

Remove business-rule validation from `Config.validate()` so the config
object is a plain data holder. Validation belongs in the workflows or a
dedicated validator, not in the configuration layer.

---

## Problem

`Config.validate()` (`src/config/config.py:83-133`) enforces business rules
such as path validation and provider selection. This is a **leaking
abstraction** — the config layer is doing work that belongs to higher-layer
coordinators or the domain.

Config should hold values. Callers should decide what's valid for their
context.

---

## Concept

Extract validation logic from `Config.validate()` into standalone validator
functions (e.g. `validate_book_path(config)`) that workflows call before
use. `Config` keeps only structural checks (required fields present, correct
types).

---

## Acceptance criteria

1. `Config.validate()` only checks structural integrity (non-None required
   fields, correct types).
2. Business-rule validation (path exists, provider is supported, etc.) lives
   in a separate validator or is checked by the calling workflow.
3. All existing tests continue to pass.
4. No behaviour change from the caller's perspective — invalid configs still
   fail before work begins.

---

## Out of scope

- Changing the config file format or adding new config fields.
- Introducing a config validation framework or library.
