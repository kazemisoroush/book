"""FastAPI app that maps HTTP calls to CLI workflows and book files."""
from dataclasses import asdict
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from src.api.runner import RunParams, WorkflowRunner
from src.config.api_config import ApiConfig
from src.domain.models import Book
from src.repository.book_repository import BookRepository
from src.repository.file_book_repository import FileBookRepository
from src.storage.keys import UnsafeKeyError, book_ids_from_keys
from src.storage.local_storage import LocalStorage
from src.storage.storage import Storage

_WORKFLOWS = frozenset(
    {"parse", "ai", "characters", "tts", "ambient", "sfx", "music", "mix"},
)
_ALLOWED_URL_SCHEMES = frozenset({"http", "https"})


class RunRequest(BaseModel):
    """Body for starting a workflow run."""
    url: str
    start_chapter: int = 1
    end_chapter: Optional[int] = None
    refresh: bool = False
    provider: Optional[str] = None


class BooksResponse(BaseModel):
    """List of known book ids."""
    books: list[str]


def create_app(
    books_dir: Path = Path("books"),
    runner: Optional[WorkflowRunner] = None,
    storage: Optional[Storage] = None,
    repository: Optional[BookRepository] = None,
    allowed_origins: Optional[list[str]] = None,
) -> FastAPI:
    """Build the API over the given storage, repository, and workflow runner."""
    books_dir = Path(books_dir)
    storage = storage or LocalStorage(books_dir)
    repository = repository or FileBookRepository(storage=storage)
    runner = runner or WorkflowRunner(books_dir)
    if allowed_origins is None:
        allowed_origins = ApiConfig.from_env().allowed_origins
    app = FastAPI(title="Book local API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["*"],
    )

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
    def get_books() -> BooksResponse:
        return BooksResponse(books=book_ids_from_keys(storage.list_prefix("")))

    @app.get("/books/{book_id}")
    def get_book(book_id: str) -> dict:
        return _load_book(repository, book_id).to_dict()

    @app.get("/books/{book_id}/files")
    def get_files(book_id: str) -> dict:
        prefix = f"{book_id}/"
        try:
            keys = storage.list_prefix(prefix)
        except UnsafeKeyError as exc:
            raise HTTPException(404, f"unknown book {book_id!r}") from exc
        return {"files": [key[len(prefix):] for key in keys]}

    @app.get("/books/{book_id}/files/{path:path}")
    def get_file(book_id: str, path: str, request: Request) -> FileResponse:
        del request
        key = f"{book_id}/{path}"
        try:
            if not storage.exists(key):
                raise HTTPException(404, f"no such file {path!r}")
            with storage.local_path(key, "r") as local:
                return FileResponse(local)
        except UnsafeKeyError as exc:
            raise HTTPException(403, "path escapes book directory") from exc

    @app.patch("/books/{book_id}/voice-assignments")
    def patch_voice_assignments(
        book_id: str, assignments: dict = Body(...),
    ) -> dict:
        book = _load_book(repository, book_id)
        for character_id, voice_id in assignments.items():
            book.voice_assignments[_as_character_id(character_id)] = voice_id
        repository.save(book)
        saved = {str(k): v for k, v in book.voice_assignments.items()}
        return {"voice_assignments": saved}

    return app


def _load_book(repository: BookRepository, book_id: str) -> Book:
    try:
        book = repository.load(book_id)
    except UnsafeKeyError as exc:
        raise HTTPException(404, f"unknown book {book_id!r}") from exc
    if book is None:
        raise HTTPException(404, f"no book.json for {book_id!r}")
    return book


def _as_character_id(raw: object) -> int:
    try:
        return int(str(raw))
    except (TypeError, ValueError) as exc:
        raise HTTPException(400, f"character id must be an integer, got {raw!r}") from exc
