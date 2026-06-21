# Stores

Persistence layer for caching fully-parsed ``Book`` models and observability artifacts. All stores delegate IO to a storage backend.

## Book Store

Abstract store for saving and loading book snapshots. Workflows read from the first store and fan writes out to every store.

### File-based Implementation

Writes `metadata.json` (pre-AI snapshot) and `book.json` (final snapshot) per book.

## Artifact Store

Unified store for AI chapter artifacts (prompts and responses) and outbound API request records with credential redaction.

### File-based Implementation

AI artifacts go under per-chapter directories. API request records are written at caller-specified keys.
