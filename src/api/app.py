"""FastAPI app that maps HTTP calls to CLI workflows and book files."""
import json
from pathlib import Path
from typing import Optional

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from src.api.files import (
    PathOutsideBookError,
    list_book_ids,
    list_files,
    resolve_within,
)
from src.api.runner import RunParams, WorkflowRunner

_WORKFLOWS = frozenset(
    {"parse", "ai", "characters", "tts", "ambient", "sfx", "music", "mix"},
)
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
) -> FastAPI:
    """Build the API bound to *books_dir* and an optional injected *runner*."""
    books_dir = Path(books_dir)
    runner = runner or WorkflowRunner(books_dir)
    app = FastAPI(title="Book local API")

    @app.post("/workflows/{name}/runs", status_code=202)
    def start_run(name: str, request: RunRequest) -> dict:
        if name not in _WORKFLOWS:
            raise HTTPException(404, f"unknown workflow {name!r}")
        params = RunParams(
            url=request.url,
            start_chapter=request.start_chapter,
            end_chapter=request.end_chapter,
            refresh=request.refresh,
            provider=request.provider,
        )
        status = runner.start(name, params)
        return _status_dict(status)

    @app.get("/runs/{run_id}")
    def get_run(run_id: str) -> dict:
        status = runner.status(run_id)
        if status is None:
            raise HTTPException(404, f"unknown run {run_id!r}")
        return _status_dict(status)

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
        return {"books": list_book_ids(books_dir)}

    @app.get("/books/{book_id}")
    def get_book(book_id: str) -> dict:
        return _read_book(books_dir, book_id)

    @app.get("/books/{book_id}/files")
    def get_files(book_id: str) -> dict:
        book_dir = books_dir / book_id
        if not book_dir.is_dir():
            raise HTTPException(404, f"unknown book {book_id!r}")
        return {"files": list_files(book_dir)}

    @app.get("/books/{book_id}/files/{path:path}")
    def get_file(book_id: str, path: str, request: Request) -> FileResponse:
        del request
        book_dir = books_dir / book_id
        if not book_dir.is_dir():
            raise HTTPException(404, f"unknown book {book_id!r}")
        try:
            target = resolve_within(book_dir, path)
        except PathOutsideBookError as exc:
            raise HTTPException(403, "path escapes book directory") from exc
        if not target.is_file():
            raise HTTPException(404, f"no such file {path!r}")
        return FileResponse(target)

    @app.patch("/books/{book_id}/voice-assignments")
    def patch_voice_assignments(
        book_id: str, assignments: dict = Body(...),
    ) -> dict:
        book = _read_book(books_dir, book_id)
        merged = {**book.get("voice_assignments", {}), **assignments}
        book["voice_assignments"] = merged
        book_path = books_dir / book_id / _BOOK_FILENAME
        book_path.write_text(json.dumps(book, indent=2), encoding="utf-8")
        return {"voice_assignments": merged}

    return app


def _read_book(books_dir: Path, book_id: str) -> dict:
    book_path = books_dir / book_id / _BOOK_FILENAME
    if not book_path.is_file():
        raise HTTPException(404, f"no book.json for {book_id!r}")
    return json.loads(book_path.read_text(encoding="utf-8"))


def _status_dict(status) -> dict:
    from dataclasses import asdict
    return asdict(status)
