# TD-006 — SQLite Persistence Backend

## Goal

Replace file-based JSON persistence with SQLite database to handle large books (61+ chapters) without exceeding file system limits or memory constraints. SQLite provides:
- Efficient schema-based storage (avoid JSON bloat)
- Transactional consistency
- Query capability for future analytics
- Proven scalability for 100MB+ datasets

---

## Problem

Current file-based persistence:
- `FileBookRepository` serializes entire `Book` object to JSON in `books/{book_id}/book.json`
- For Pride & Prejudice (61 chapters, 1000+ characters, full scene/ambient/SFX metadata), JSON exceeds 50MB
- Parsing and deserializing 50MB+ JSON files becomes slow and memory-intensive
- No query capability: can't inspect parsed chapters without full deserialization
- No streaming: must load entire book into memory

---

## Concept

**SQLite Database Schema**:

```sql
CREATE TABLE books (
    id TEXT PRIMARY KEY,           -- book_id
    title TEXT,
    author TEXT,
    language TEXT,
    created_at DATETIME,
    updated_at DATETIME
);

CREATE TABLE chapters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id TEXT NOT NULL,
    chapter_number INTEGER,        -- 1-based
    title TEXT,
    created_at DATETIME,
    FOREIGN KEY (book_id) REFERENCES books(id)
);

CREATE TABLE sections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_id INTEGER NOT NULL,
    section_index INTEGER,
    text TEXT,
    section_type TEXT,             -- enum: NARRATION, DIALOGUE, etc.
    created_at DATETIME,
    FOREIGN KEY (chapter_id) REFERENCES chapters(id)
);

CREATE TABLE segments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    section_id INTEGER NOT NULL,
    segment_index INTEGER,
    text TEXT,
    segment_type TEXT,             -- enum: NARRATION, DIALOGUE, etc.
    character_id TEXT,
    emotion TEXT,
    voice_stability REAL,
    voice_style REAL,
    voice_speed REAL,
    scene_id TEXT,
    sound_effect_description TEXT,
    created_at DATETIME,
    FOREIGN KEY (section_id) REFERENCES sections(id)
);

CREATE TABLE characters (
    id TEXT PRIMARY KEY,           -- character_id
    book_id TEXT NOT NULL,
    name TEXT,
    is_narrator BOOLEAN,
    sex TEXT,
    age TEXT,
    description TEXT,
    voice_design_prompt TEXT,
    created_at DATETIME,
    FOREIGN KEY (book_id) REFERENCES books(id)
);

CREATE TABLE scenes (
    id TEXT PRIMARY KEY,           -- scene_id
    book_id TEXT NOT NULL,
    environment TEXT,
    acoustic_hints TEXT,
    voice_modifiers_json TEXT,     -- JSON: {stability_delta, style_delta, speed}
    ambient_prompt TEXT,
    ambient_volume REAL,
    created_at DATETIME,
    FOREIGN KEY (book_id) REFERENCES books(id)
);
```

**Dual Repository Interface**:

- Keep `FileBookRepository` for backward compatibility
- New `SQLiteBookRepository` implementing same interface (`save()`, `load()`, `exists()`)
- `FileBookRepository` remains default; users opt-in to SQLite via config or CLI flag
- Both repositories coexist; no forced migration

---

## Acceptance Criteria

1. New `src/repository/sqlite_book_repository.py` module implementing `BookRepository` interface
2. SQLite database stored at `{base_dir}/{book_id}.db` (one DB file per book)
3. `SQLiteBookRepository.save(book, book_id)` stores entire book structure efficiently
4. `SQLiteBookRepository.load(book_id)` reconstructs full `Book` object identical to original
5. `SQLiteBookRepository.exists(book_id)` returns True if `.db` file exists
6. Serialization round-trip test: save then load produces bit-identical result
7. New CLI flag: `--repository sqlite` (defaults to `--repository file`)
8. Config support: `config/features.yaml` can specify repository backend
9. Performance benchmark:
   - Save 61-chapter book: < 2 seconds (vs ~30 seconds for 50MB JSON)
   - Load 61-chapter book: < 2 seconds (vs ~30 seconds)
10. All existing tests pass; `FileBookRepository` remains default
11. Integration test: Parse Pride & Prejudice (61 chapters) to SQLite, verify size < 10MB

---

## Out of Scope

- Analytics queries on parsed data (future enhancement)
- Schema versioning/migrations (v1 only)
- Concurrent access (single-writer assumption)
- Data export to other formats

---

## Files Changed (Expected)

| File | Change |
|---|---|
| `src/repository/sqlite_book_repository.py` | **NEW** — SQLite implementation of `BookRepository` |
| `src/repository/__init__.py` | Export `SQLiteBookRepository` |
| `scripts/run_workflow.py` | Add `--repository sqlite\|file` CLI flag |
| `src/workflows/ai_project_gutenberg_workflow.py` | Accept `repository_backend` parameter |
| `src/config/feature_flags.py` | Add `repository_backend` to FeatureFlags dataclass |
| `config/features.example.yaml` | Add `repository_backend: file` example |
| `src/repository/sqlite_book_repository_test.py` | **NEW** — Unit tests for SQLite repo |

---

## Implementation Notes

- Use Python's built-in `sqlite3` module (no new dependencies)
- Transactions: wrap save operations in `BEGIN; ...; COMMIT` for atomicity
- JSON columns: Store complex nested structures (voice_modifiers, character descriptions) as JSON strings; parse on retrieval
- Foreign keys: Enable via `PRAGMA foreign_keys = ON` at connection time
- Type mappings:
  - Python `bool` → SQLite `BOOLEAN (0/1)`
  - Python `Optional[str]` → SQLite `TEXT NULL`
  - Python `float` → SQLite `REAL`
  - Enums (SegmentType, etc.) → SQLite `TEXT`
- Backward compatibility: `FileBookRepository` remains unchanged and is default

---

## Success Criteria

Users can:
1. Run `make ai CHAPTERS=61 --repository sqlite` and complete without OOM errors
2. See SQLite database file at `books/Pride\ and\ Prejudice\ -\ Jane\ Austen/db` (< 10MB)
3. Resume interrupted runs with `--repository sqlite --resume` and get identical output
4. Optionally use `--repository file` (default) for backward compatibility
5. Not experience any performance regression compared to file-based storage

