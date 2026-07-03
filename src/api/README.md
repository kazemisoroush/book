# API

A thin local HTTP server that is a remote control over the CLI. It never holds pipeline logic and never calls ElevenLabs, Anthropic, or AWS. Every action maps to a CLI workflow subprocess or a file under `books/{book_id}/`.

## WorkflowRunner

`runner.py` starts `python main.py --workflow ...` as a subprocess. Run state lives on disk under `books/.runs/{run_id}/` as `status.json` and `log.ndjson`, so nothing is kept in memory. A background thread waits for the process and records the final state as `succeeded` or `failed`.

## create_app

`app.py` builds the FastAPI app. It talks only in book ids and storage keys. It reads and writes books through `BookRepository` and lists and serves artifact files through `Storage`, so the same routes work against a remote storage backend later. Key safety is a storage concern: `ensure_safe_key` in `src/storage/keys.py` rejects absolute or escaping keys inside every backend, so the API does no path math and maps an unsafe key to a `404` or `403`. The `voice_assignments` write goes through the `Book` model, which already carries that field. Audio files are served with a real path from `Storage.local_path`, and Starlette `FileResponse` answers HTTP range requests for seeking. The runner keeps its own run files on local disk, since live log streaming reads a local file as it is written.

| Method | Path | Purpose |
| ------ | ---- | ------- |
| POST | `/workflows/{name}/runs` | Start a workflow run and return its status. |
| GET | `/runs/{run_id}` | Read run status. |
| GET | `/runs/{run_id}/logs` | Stream logs as Server-Sent Events. |
| GET | `/books` | List book ids. |
| GET | `/books/{book_id}` | Return `book.json`. |
| GET | `/books/{book_id}/files` | List artifact files. |
| GET | `/books/{book_id}/files/{path}` | Serve a file with range support. |
| PATCH | `/books/{book_id}/voice-assignments` | Merge voice assignments into `book.json`. |

## Running

`make serve` starts the server on `127.0.0.1:8000`. Set `API_HOST` and `API_PORT` to change the bind address.
