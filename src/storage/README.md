# Storage

Key-addressed object store. Every file the higher-level stores write goes through this seam so swapping the local filesystem for S3 means implementing one interface.

## Storage

Abstract key-and-bytes interface for reading, writing, and listing objects.

## LocalFileStorage

Filesystem-backed implementation. Construct with the base directory the keys are relative to.

## Higher-level stores

Compose `Storage` with their own layout. See [stores](../stores/README.md). To target S3, write one `S3Storage` and rewire `workflow_factory`.
