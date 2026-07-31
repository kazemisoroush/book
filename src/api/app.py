"""FastAPI app that maps HTTP calls to CLI workflows and book files."""
import threading
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
from src.domain.beat import Beat
from src.domain.character import NARRATOR_ID, NARRATOR_NAME
from src.domain.character_registry import CharacterRegistry
from src.domain.models import Book, Chapter
from src.repository.book_repository import BookRepository
from src.repository.file_book_repository import FileBookRepository
from src.storage.keys import UnsafeKeyError, book_ids_from_keys
from src.storage.storage import Storage
from src.storage.storage_factory import create_storage

_WORKFLOWS = frozenset(
    {
        "parse", "ai", "characters", "casting-candidates", "tts",
        "ambient", "sfx", "music", "mix",
    },
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


class SectionView(BaseModel):
    """One parsed source paragraph from the input snapshot."""
    text: str
    section_type: Optional[str] = None


class BeatView(BaseModel):
    """One AI-produced beat with its resolved speaker, for the attribution review."""
    index: int
    character_id: Optional[int] = None
    character_name: str
    beat_type: str
    text: str
    emotion: Optional[str] = None


class CastMember(BaseModel):
    """A speaker in a chapter and how many beats they carry, for the cast legend."""
    id: Optional[int] = None
    name: str
    count: int


class ChapterDetail(BaseModel):
    """A chapter's parsed sections beside its beats and cast, for the attribution review."""
    number: int
    title: str = ""
    sections: list[SectionView]
    beats: list[BeatView]
    cast: list[CastMember]


class BeatPatch(BaseModel):
    """A change to one beat: any of its speaker, text, or emotion. Unset fields are left as-is."""
    character_id: Optional[int] = None
    text: Optional[str] = None
    emotion: Optional[str] = None


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
    # Book edits are whole-file load-modify-save, and FastAPI runs the sync handlers concurrently.
    # This serializes the writes so overlapping edits (e.g. the per-beat autosave) cannot clobber
    # each other on disk.
    write_lock = threading.Lock()
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
        return _book_detail(book_id, book, _load_input_book(repository, book_id))

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
        with write_lock:
            book = _load_book(repository, book_id)
            for character_id, voice_id in assignments.items():
                book.voice_assignments[_as_character_id(character_id)] = voice_id
            repository.save(book)
        saved = {str(k): v for k, v in book.voice_assignments.items()}
        return {"voice_assignments": saved}

    @app.get("/books/{book_id}/chapters/{number}")
    def get_chapter(book_id: str, number: int) -> ChapterDetail:
        # Sections (the parsed paragraphs) come from the input snapshot. Beats come from the
        # AI-processed output, so a chapter parsed but not yet beated has sections and no beats.
        book = _load_book(repository, book_id)
        input_book = _load_input_book(repository, book_id)
        output_chapter = _find_chapter(book, number)
        input_chapter = _find_chapter(input_book, number)
        if output_chapter is None and input_chapter is None:
            raise HTTPException(404, f"no chapter {number} in {book_id!r}")
        return _chapter_detail(
            number, input_chapter or output_chapter, output_chapter, book.character_registry,
        )

    @app.patch("/books/{book_id}/chapters/{number}/beats/{index}")
    def patch_beat(
        book_id: str, number: int, index: int, patch: BeatPatch = Body(...),
    ) -> BeatView:
        changes = patch.model_dump(exclude_unset=True)
        if not changes:
            raise HTTPException(400, "no beat fields to update")
        with write_lock:
            book = _load_book(repository, book_id)
            chapter = _find_chapter(book, number)
            if chapter is None:
                raise HTTPException(404, f"no chapter {number} in {book_id!r}")
            if not 0 <= index < len(chapter.beats):
                raise HTTPException(404, f"no beat {index} in chapter {number} of {book_id!r}")
            beat = chapter.beats[index]
            if "character_id" in changes:
                beat.character_id = _validate_character_id(changes["character_id"], book)
            if "text" in changes:
                beat.text = changes["text"]
            if "emotion" in changes:
                beat.emotion = changes["emotion"]
            repository.save(book)
            return _beat_view(index, beat, book.character_registry)

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


def _load_input_book(repository: BookRepository, book_id: str) -> Optional[Book]:
    """Load the input (parse) snapshot, or None when it is missing or unreadable.

    A book always has an output snapshot but may lack a readable input one, so callers merge what
    the input adds (the parsed sections) over the output rather than requiring it.
    """
    try:
        return repository.load_input(book_id)
    except (ValueError, KeyError):
        logger.warning("ignoring_unreadable_input_snapshot", book_id=book_id)
        return None


def _as_character_id(raw: object) -> int:
    try:
        return int(str(raw))
    except (TypeError, ValueError) as exc:
        raise HTTPException(400, f"character id must be an integer, got {raw!r}") from exc


def _find_chapter(book: Optional[Book], number: int) -> Optional[Chapter]:
    if book is None:
        return None
    for chapter in book.content.chapters:
        if chapter.number == number:
            return chapter
    return None


def _chapter_detail(
    number: int,
    sections_source: Optional[Chapter],
    beats_source: Optional[Chapter],
    registry: CharacterRegistry,
) -> ChapterDetail:
    sections = [
        SectionView(text=s.text, section_type=s.section_type)
        for s in (sections_source.sections if sections_source else [])
    ]
    beats = beats_source.beats if beats_source else []
    title = (sections_source.title if sections_source else "") or (
        beats_source.title if beats_source else ""
    )
    return ChapterDetail(
        number=number,
        title=title or "",
        sections=sections,
        beats=[_beat_view(i, beat, registry) for i, beat in enumerate(beats)],
        cast=_chapter_cast(beats, registry),
    )


def _beat_view(index: int, beat: Beat, registry: CharacterRegistry) -> BeatView:
    return BeatView(
        index=index,
        character_id=beat.character_id,
        character_name=_speaker_name(beat.character_id, registry),
        beat_type=beat.beat_type.value,
        text=beat.text,
        emotion=beat.emotion,
    )


def _speaker_name(character_id: Optional[int], registry: CharacterRegistry) -> str:
    # A beat with no character is the narrator. An id absent from the registry is a data slip we
    # label rather than hide, so a reviewer can see and reassign it.
    if character_id is None:
        return NARRATOR_NAME
    character = registry.get(character_id)
    return character.name if character is not None else f"Character {character_id}"


def _chapter_cast(beats: list[Beat], registry: CharacterRegistry) -> list[CastMember]:
    counts: dict[Optional[int], int] = {}
    for beat in beats:
        counts[beat.character_id] = counts.get(beat.character_id, 0) + 1
    members = [
        CastMember(id=cid, name=_speaker_name(cid, registry), count=count)
        for cid, count in counts.items()
    ]
    members.sort(key=lambda m: m.count, reverse=True)
    return members


def _validate_character_id(character_id: Optional[int], book: Book) -> Optional[int]:
    # None is the narrator. Any other id must name a known character, so a reassign cannot point a
    # beat at a speaker that does not exist.
    if character_id is None or character_id == NARRATOR_ID:
        return character_id
    if book.character_registry.get(character_id) is None:
        raise HTTPException(400, f"unknown character id {character_id}")
    return character_id
