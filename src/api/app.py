"""FastAPI app that maps HTTP calls to CLI workflows and book files."""
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from fastapi import Body, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from src.api.runner import RunParams, RunStatus, WorkflowRunner
from src.config.api_config import ApiConfig
from src.domain.models import Book
from src.repository.book_repository import BookRepository
from src.repository.file_book_repository import FileBookRepository
from src.storage.keys import UnsafeKeyError, book_ids_from_keys
from src.storage.storage import Storage
from src.storage.storage_factory import create_storage

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


class HealthResponse(BaseModel):
    """Liveness signal for the platform."""
    status: str


class BooksResponse(BaseModel):
    """List of known book ids."""
    books: list[str]


class ChapterSummary(BaseModel):
    """One chapter's number and title."""
    number: int
    title: str = ""


class CharacterInfo(BaseModel):
    """A character and the voice traits the AI assigned."""
    id: int
    name: str
    gender: Optional[str] = None
    age: Optional[str] = None
    accent: Optional[str] = None


class BookDetail(BaseModel):
    """A book's metadata, chapters, characters, and recorded voice assignments."""
    id: str
    title: str
    author: Optional[str] = None
    chapters: list[ChapterSummary]
    characters: list[CharacterInfo]
    voice_assignments: dict[str, str]


class FilesResponse(BaseModel):
    """Relative paths of a book's artifact files."""
    files: list[str]


class RunStatusResponse(BaseModel):
    """The state of a workflow run."""
    run_id: str
    workflow: str
    state: str
    returncode: Optional[int] = None
    started_at: str = ""
    ended_at: Optional[str] = None


class RunLogsResponse(BaseModel):
    """A page of run log lines and the cursor to fetch the next page."""
    lines: list[str]
    cursor: int
    done: bool


def create_app(
    books_dir: Path = Path("books"),
    runner: Optional[WorkflowRunner] = None,
    storage: Optional[Storage] = None,
    repository: Optional[BookRepository] = None,
    allowed_origins: Optional[list[str]] = None,
) -> FastAPI:
    """Build the API over the given storage, repository, and workflow runner."""
    books_dir = Path(books_dir)
    storage = storage or create_storage(books_dir)
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

    @app.get("/health")
    def health() -> HealthResponse:
        return HealthResponse(status="ok")

    @app.post("/workflows/{name}/runs", status_code=202)
    def start_run(name: str, request: RunRequest) -> RunStatusResponse:
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
        return _run_status(runner.start(name, params))

    @app.get("/runs/{run_id}")
    def get_run(run_id: str) -> RunStatusResponse:
        status = runner.status(run_id)
        if status is None:
            raise HTTPException(404, f"unknown run {run_id!r}")
        return _run_status(status)

    @app.get("/runs/{run_id}/logs")
    def get_logs(
        run_id: str, cursor: int = Query(0, ge=0),
    ) -> RunLogsResponse:
        status = runner.status(run_id)
        if status is None:
            raise HTTPException(404, f"unknown run {run_id!r}")
        lines, next_cursor = runner.read_logs(
            run_id, cursor, flush=status.is_terminal,
        )
        return RunLogsResponse(lines=lines, cursor=next_cursor, done=status.is_terminal)

    @app.get("/books")
    def get_books() -> BooksResponse:
        return BooksResponse(books=book_ids_from_keys(storage.list_prefix("")))

    @app.get("/books/{book_id}")
    def get_book(book_id: str) -> BookDetail:
        return _book_detail(book_id, _load_book(repository, book_id))

    @app.get("/books/{book_id}/files")
    def get_files(book_id: str) -> FilesResponse:
        prefix = f"{book_id}/"
        try:
            keys = storage.list_prefix(prefix)
        except UnsafeKeyError as exc:
            raise HTTPException(404, f"unknown book {book_id!r}") from exc
        return FilesResponse(files=[key[len(prefix):] for key in keys])

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


def _book_detail(book_id: str, book: Book) -> BookDetail:
    return BookDetail(
        id=book_id,
        title=book.metadata.title,
        author=book.metadata.author,
        chapters=[
            ChapterSummary(number=c.number, title=c.title or "")
            for c in book.content.chapters
        ],
        characters=[
            CharacterInfo(
                id=c.id, name=c.name,
                gender=c.gender, age=c.age, accent=c.accent,
            )
            for c in book.character_registry.characters
        ],
        voice_assignments={str(k): v for k, v in book.voice_assignments.items()},
    )


def _run_status(status: RunStatus) -> RunStatusResponse:
    return RunStatusResponse(
        run_id=status.run_id,
        workflow=status.workflow,
        state=status.state,
        returncode=status.returncode,
        started_at=status.started_at,
        ended_at=status.ended_at,
    )


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
