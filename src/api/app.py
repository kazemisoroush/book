"""FastAPI app that maps HTTP calls to CLI workflows and book files."""
from dataclasses import asdict
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from src.api.files import (
    PathOutsideBookError,
    book_ids_from_keys,
    resolve_book_dir,
    resolve_within,
)
from src.api.runner import RunParams, WorkflowRunner
from src.repository.book_repository import BookRepository
from src.repository.file_book_repository import FileBookRepository
from src.storage.local_storage import LocalStorage
from src.storage.storage import Storage

_WORKFLOWS = frozenset(
    {"parse", "ai", "characters", "tts", "ambient", "sfx", "music", "mix"},
)
_ALLOWED_URL_SCHEMES = frozenset({"http", "https"})
_BOOK_FILENAME = "book.json"


class RunRequest(BaseModel):
    """Body for starting a workflow run."""
    url: str
    start_chapter: int = 1
    end_chapter: Optional[int] = None
    refresh: bool = False
    provider: Optional[str] = None


def create_app(
    books_dir: Path = Path("books"),
    runner: Optional[WorkflowRunner] = None,
    storage: Optional[Storage] = None,
    repository: Optional[BookRepository] = None,
) -> FastAPI:
    """Build the API over the given storage, repository, and workflow runner."""
    books_dir = Path(books_dir)
    storage = storage or LocalStorage(books_dir)
    repository = repository or FileBookRepository(storage=storage)
    runner = runner or WorkflowRunner(books_dir)
    base_dir = books_dir.resolve()
    app = FastAPI(title="Book local API")

    @app.post("/workflows/{name}/runs", status_code=202)
    def start_run(name: str, request: RunRequest) -> dict:
        if name not in _WORKFLOWS:
            raise HTTPException(404, f"unknown workflow {name!r}")
        if urlparse(request.url).scheme not in _ALLOWED_URL_SCHEMES:
            raise HTTPException(400, "url must be an http or https address")
        params = RunParams(
            url=request.url,
            start_chapter=request.start_chapter,
            end_chapter=request.end_chapter,
            refresh=request.refresh,
            provider=request.provider,
        )
        return asdict(runner.start(name, params))

    @app.get("/runs/{run_id}")
    def get_run(run_id: str) -> dict:
        status = runner.status(run_id)
        if status is None:
            raise HTTPException(404, f"unknown run {run_id!r}")
        return asdict(status)

    @app.get("/runs/{run_id}/logs")
    def stream_logs(run_id: str) -> StreamingResponse:
        if runner.status(run_id) is None:
            raise HTTPException(404, f"unknown run {run_id!r}")

        def events():
            for line in runner.tail(run_id):
                yield f"data: {line.rstrip(chr(10))}\n\n"
            yield "event: end\ndata: {}\n\n"

        return StreamingResponse(events(), media_type="text/event-stream")

    @app.get("/books")
    def get_books() -> dict:
        return {"books": book_ids_from_keys(storage.list_prefix(""))}

    @app.get("/books/{book_id}")
    def get_book(book_id: str) -> dict:
        _validate_book_id(base_dir, book_id)
        book = repository.load(book_id)
        if book is None:
            raise HTTPException(404, f"no book.json for {book_id!r}")
        return book.to_dict()

    @app.get("/books/{book_id}/files")
    def get_files(book_id: str) -> dict:
        _validate_book_id(base_dir, book_id)
        prefix = f"{book_id}/"
        keys = storage.list_prefix(prefix)
        return {"files": [key[len(prefix):] for key in keys]}

    @app.get("/books/{book_id}/files/{path:path}")
    def get_file(book_id: str, path: str, request: Request) -> FileResponse:
        del request
        key = _file_key(base_dir, book_id, path)
        if not storage.exists(key):
            raise HTTPException(404, f"no such file {path!r}")
        with storage.local_path(key, "r") as local:
            return FileResponse(local)

    @app.patch("/books/{book_id}/voice-assignments")
    def patch_voice_assignments(
        book_id: str, assignments: dict = Body(...),
    ) -> dict:
        _validate_book_id(base_dir, book_id)
        book = repository.load(book_id)
        if book is None:
            raise HTTPException(404, f"no book.json for {book_id!r}")
        for character_id, voice_id in assignments.items():
            book.voice_assignments[_as_character_id(character_id)] = voice_id
        repository.save(book)
        saved = {str(k): v for k, v in book.voice_assignments.items()}
        return {"voice_assignments": saved}

    return app


def _validate_book_id(base_dir: Path, book_id: str) -> None:
    try:
        resolve_book_dir(base_dir, book_id)
    except PathOutsideBookError as exc:
        raise HTTPException(404, f"unknown book {book_id!r}") from exc


def _file_key(base_dir: Path, book_id: str, path: str) -> str:
    book_dir = _validate_book_dir(base_dir, book_id)
    try:
        target = resolve_within(book_dir, path)
    except PathOutsideBookError as exc:
        raise HTTPException(403, "path escapes book directory") from exc
    return target.relative_to(base_dir.resolve()).as_posix()


def _validate_book_dir(base_dir: Path, book_id: str) -> Path:
    try:
        return resolve_book_dir(base_dir, book_id)
    except PathOutsideBookError as exc:
        raise HTTPException(404, f"unknown book {book_id!r}") from exc


def _as_character_id(raw: object) -> int:
    try:
        return int(str(raw))
    except (TypeError, ValueError) as exc:
        raise HTTPException(400, f"character id must be an integer, got {raw!r}") from exc
