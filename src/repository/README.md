# Repository

Persistence layer for caching fully-parsed ``Book`` models and observability artifacts. All repositories delegate IO to a storage backend.

## Book Repository

Abstract repository for saving and loading book snapshots. Workflows read from the first repository and fan writes out to every repository.

### File-based Implementation

Writes `metadata.json` (pre-AI snapshot) and `book.json` (final snapshot) per book.

## Artifact Repository

Unified repository for AI chapter artifacts (prompts and responses) and outbound API request records with credential redaction.

### File-based Implementation

AI artifacts go under per-chapter directories. API request records are written at caller-specified keys.
