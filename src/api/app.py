"""FastAPI app that maps HTTP calls to CLI workflows and book files."""
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import structlog
from fastapi import Body, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from src.api.lambda_runner import LambdaWorkflowRunner
from src.api.run_store import RunStore
from src.api.runner import Runner, RunParams, RunStatus, WorkflowRunner
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

# A run still "running" past this is treated as failed. The worker Lambda caps at 15 minutes,
# so a longer-lived running record means the worker died without recording a terminal state.
_STALE_AFTER_SECONDS = 20 * 60

logger = structlog.get_logger(__name__)


class RunRequest(BaseModel):
    """Body for starting a workflow run."""
    url: str
    start_chapter: int = 1
    end_chapter: Optional[int] = None
    refresh: bool = False
    provider: Optional[str] = None
    book_id: Optional[str] = None


class HealthResponse(BaseModel):
    """Liveness signal for the platform."""
    status: str


class BookSummary(BaseModel):
    """A book's headline metadata and casting counts for the list view."""
    id: str
    title: str
    author: Optional[str] = None
    language: Optional[str] = None
    release_date: Optional[str] = None
    chapters: int
    characters: int
    cast: int


class BooksResponse(BaseModel):
    """The known books with their metadata."""
    books: list[BookSummary]


class ChapterSummary(BaseModel):
    """One chapter's number, title, and how many beats have been extracted."""
    number: int
    title: str = ""
    beats: int = 0


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
    source_url: Optional[str] = None
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


class RunSummary(BaseModel):
    """One run's state for a book, so the chapters table can show live progress."""
    run_id: str
    workflow: str
    start_chapter: Optional[int] = None
    end_chapter: Optional[int] = None
    state: str
    started_at: str = ""
    ended_at: Optional[str] = None


class RunsResponse(BaseModel):
    """The runs recorded for a book, oldest first."""
    runs: list[RunSummary]


def create_app(
    books_dir: Path = Path("books"),
    runner: Optional[Runner] = None,
    storage: Optional[Storage] = None,
    repository: Optional[BookRepository] = None,
    allowed_origins: Optional[list[str]] = None,
) -> FastAPI:
    """Build the API over the given storage, repository, and workflow runner."""
    books_dir = Path(books_dir)
    api_config = ApiConfig.from_env()
    storage = storage or create_storage(books_dir)
    repository = repository or FileBookRepository(storage=storage)
    run_store = RunStore(storage)
    if runner is None:
        if api_config.worker_function_name:
            runner = LambdaWorkflowRunner(api_config.worker_function_name, storage)
        else:
            runner = WorkflowRunner(books_dir)
    if allowed_origins is None:
        allowed_origins = api_config.allowed_origins
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
            book_id=request.book_id,
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
        summaries = []
        for book_id in book_ids_from_keys(storage.list_prefix("")):
            try:
                book = repository.load(book_id)
            except (ValueError, KeyError):
                logger.warning("skipping_unreadable_book", book_id=book_id)
                continue  # a malformed book.json is not a listable book
            if book is not None:
                summaries.append(_book_summary(book_id, book))
        return BooksResponse(books=summaries)

    @app.get("/books/{book_id}")
    def get_book(book_id: str) -> BookDetail:
        book = _load_book(repository, book_id)
        try:
            input_book = repository.load_input(book_id)
        except (ValueError, KeyError):
            logger.warning("ignoring_unreadable_input_snapshot", book_id=book_id)
            input_book = None
        return _book_detail(book_id, book, input_book)

    @app.get("/books/{book_id}/runs")
    def get_book_runs(book_id: str) -> RunsResponse:
        runs = run_store.list_for_book(book_id)
        return RunsResponse(runs=[_run_summary(run) for run in runs])

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


def _book_summary(book_id: str, book: Book) -> BookSummary:
    return BookSummary(
        id=book_id,
        title=book.metadata.title,
        author=book.metadata.display_author,
        language=book.metadata.language,
        release_date=book.metadata.releaseDate,
        chapters=len(book.content.chapters),
        characters=len(book.character_registry.characters),
        cast=len(book.voice_assignments),
    )


def _book_detail(book_id: str, book: Book, input_book: Optional[Book]) -> BookDetail:
    # The complete chapter list comes from the parse (input snapshot). Beat counts come from the
    # AI-processed output. Fall back to the output when the input snapshot is missing or empty.
    beats_by_number = {c.number: len(c.beats) for c in book.content.chapters}
    full_chapters = (
        input_book.content.chapters
        if input_book is not None and input_book.content.chapters
        else book.content.chapters
    )
    return BookDetail(
        id=book_id,
        title=book.metadata.title,
        author=book.metadata.display_author,
        source_url=book.source_url,
        chapters=[
            ChapterSummary(
                number=c.number, title=c.title or "",
                beats=beats_by_number.get(c.number, 0),
            )
            for c in full_chapters
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


def _run_summary(run: RunStatus) -> RunSummary:
    return RunSummary(
        run_id=run.run_id,
        workflow=run.workflow,
        start_chapter=run.params.get("start_chapter"),
        end_chapter=run.params.get("end_chapter"),
        state=run.effective_state(datetime.now(timezone.utc), _STALE_AFTER_SECONDS),
        started_at=run.started_at,
        ended_at=run.ended_at,
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
