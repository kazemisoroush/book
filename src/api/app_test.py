"""Tests for the local API routes."""
import json
import sys
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from src.api.app import create_app
from src.api.run_store import RunStore
from src.api.runner import RUNNING, SUCCEEDED, RunStatus, WorkflowRunner
from src.domain.models import Book, BookContent, BookMetadata
from src.repository.file_book_repository import FileBookRepository
from src.storage.local_storage import LocalStorage


def _client(tmp_path):
    runner = WorkflowRunner(
        tmp_path,
        command_prefix=[sys.executable, "-c", "pass"],
        cwd=tmp_path,
    )
    return TestClient(create_app(books_dir=tmp_path, runner=runner))


def _seed_book(tmp_path, book_id="the_gambler", body=None):
    book_dir = tmp_path / book_id
    book_dir.mkdir(parents=True)
    payload = body if body is not None else {
        "metadata": {"title": "The Gambler"},
        "content": {"chapters": []},
    }
    (book_dir / "book.json").write_text(json.dumps(payload))
    return book_dir


def test_health_reports_ok(tmp_path):
    # Arrange
    client = _client(tmp_path)

    # Act
    response = client.get("/health")

    # Assert
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_start_run_returns_accepted_status(tmp_path):
    # Arrange
    client = _client(tmp_path)

    # Act
    response = client.post(
        "/workflows/parse/runs", json={"url": "http://example/pg.zip"},
    )

    # Assert
    assert response.status_code == 202
    assert response.json()["state"] == "running"


def test_cors_headers_present_for_allowed_origin(tmp_path):
    # Arrange
    runner = WorkflowRunner(
        tmp_path, command_prefix=[sys.executable, "-c", "pass"], cwd=tmp_path,
    )
    client = TestClient(
        create_app(
            books_dir=tmp_path, runner=runner,
            allowed_origins=["http://localhost:3000"],
        ),
    )

    # Act
    response = client.get("/books", headers={"Origin": "http://localhost:3000"})

    # Assert
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_start_run_rejects_unknown_workflow(tmp_path):
    # Arrange
    client = _client(tmp_path)

    # Act
    response = client.post(
        "/workflows/bogus/runs", json={"url": "http://example/pg.zip"},
    )

    # Assert
    assert response.status_code == 404


def test_get_unknown_run_is_404(tmp_path):
    # Arrange
    client = _client(tmp_path)

    # Act
    response = client.get("/runs/nope")

    # Assert
    assert response.status_code == 404


def test_list_books_returns_metadata(tmp_path):
    # Arrange
    _seed_book(
        tmp_path, "wuthering_heights",
        body={
            "metadata": {
                "title": "Wuthering Heights",
                "author": "Brontë, Emily, 1818-1848",
                "language": "en",
                "releaseDate": "1996-12-01",
            },
            "content": {"chapters": [{"number": 1, "title": "Chapter One"}]},
            "character_registry": [
                {"id": 1, "name": "Heathcliff"},
                {"id": 2, "name": "Catherine"},
            ],
            "voice_assignments": {"1": "voice-a"},
        },
    )
    client = _client(tmp_path)

    # Act
    response = client.get("/books")

    # Assert
    assert response.status_code == 200
    assert response.json()["books"] == [
        {
            "id": "wuthering_heights",
            "title": "Wuthering Heights",
            "author": "Emily Brontë",
            "language": "en",
            "release_date": "1996-12-01",
            "chapters": 1,
            "characters": 2,
            "cast": 1,
        },
    ]


def test_list_books_skips_control_directories(tmp_path):
    # Arrange: an underscore-prefixed shared cache is not a book.
    _seed_book(tmp_path, "dracula", body={
        "metadata": {"title": "Dracula"}, "content": {"chapters": []},
    })
    shared = tmp_path / "_shared_voices"
    shared.mkdir(parents=True)
    (shared / "voices.json").write_text("{}")
    client = _client(tmp_path)

    # Act
    response = client.get("/books")

    # Assert
    ids = [book["id"] for book in response.json()["books"]]
    assert ids == ["dracula"]


def test_get_book_returns_detail(tmp_path):
    # Arrange
    _seed_book(
        tmp_path, "the_gambler",
        body={
            "metadata": {"title": "The Gambler", "author": "Fyodor Dostoyevsky"},
            "source_url": "http://example/pg.zip",
            "content": {"chapters": [{"number": 1, "title": "Chapter One"}]},
            "character_registry": [
                {"id": 1, "name": "Narrator", "gender": "male",
                 "age": "old", "accent": "russian"},
            ],
            "voice_assignments": {"1": "voice-a"},
        },
    )
    client = _client(tmp_path)

    # Act
    response = client.get("/books/the_gambler")

    # Assert
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "The Gambler"
    assert body["author"] == "Fyodor Dostoyevsky"
    assert body["source_url"] == "http://example/pg.zip"
    assert body["chapters"] == [{"number": 1, "title": "Chapter One", "beats": 0}]
    assert body["characters"][0]["name"] == "Narrator"
    assert body["characters"][0]["accent"] == "russian"
    assert body["voice_assignments"] == {"1": "voice-a"}


def test_get_book_lists_all_parsed_chapters_with_beats(tmp_path):
    # Arrange: the output snapshot (book.json) holds only the AI-processed chapter 1.
    # The input snapshot (metadata.json) holds the full three-chapter parse.
    _seed_book(
        tmp_path, "the_gambler",
        body={
            "metadata": {"title": "The Gambler"},
            "content": {"chapters": [
                {"number": 1, "title": "Chapter One", "beats": [
                    {"text": "A.", "beat_type": "book_title_announcement"},
                    {"text": "B.", "beat_type": "book_title_announcement"},
                ]},
            ]},
        },
    )
    (tmp_path / "the_gambler" / "metadata.json").write_text(json.dumps({
        "metadata": {"title": "The Gambler"},
        "content": {"chapters": [
            {"number": 1, "title": "Chapter One"},
            {"number": 2, "title": "Chapter Two"},
            {"number": 3, "title": "Chapter Three"},
        ]},
    }))
    client = _client(tmp_path)

    # Act
    response = client.get("/books/the_gambler")

    # Assert
    chapters = response.json()["chapters"]
    assert [c["number"] for c in chapters] == [1, 2, 3]
    assert chapters[0]["beats"] == 2  # from the AI-processed output snapshot
    assert chapters[1]["beats"] == 0  # parsed, not yet processed


def test_get_book_falls_back_when_input_snapshot_is_corrupt(tmp_path):
    # Arrange: a valid output snapshot with a broken input snapshot beside it.
    _seed_book(
        tmp_path, "the_gambler",
        body={
            "metadata": {"title": "The Gambler"},
            "content": {"chapters": [{"number": 1, "title": "Chapter One"}]},
        },
    )
    (tmp_path / "the_gambler" / "metadata.json").write_text("{ not valid json")
    client = _client(tmp_path)

    # Act
    response = client.get("/books/the_gambler")

    # Assert: the output snapshot's chapters are served, not a 500.
    assert response.status_code == 200
    assert [c["number"] for c in response.json()["chapters"]] == [1]


# A book is stored under its metadata-derived id (``title:author``). A PATCH re-saves under that
# same id, so the seed folder must be the derived id for the round-trip to land in one place.
_BEATED_BOOK_ID = "the_gambler:fyodor_dostoyevsky"
_BEATED_META = {"title": "The Gambler", "author": "Fyodor Dostoyevsky"}


def _seed_beated_chapter(tmp_path, book_id=_BEATED_BOOK_ID):
    # book.json: the AI output with three beats (narrator, dialogue, narrator).
    _seed_book(
        tmp_path, book_id,
        body={
            "metadata": _BEATED_META,
            "content": {"chapters": [{"number": 1, "title": "Chapter One", "beats": [
                {"text": "He walked out.", "beat_type": "narration",
                 "character_id": 1, "emotion": "measured"},
                {"text": "Where to?", "beat_type": "dialogue",
                 "character_id": 2, "emotion": "curious"},
                {"text": "she asked.", "beat_type": "narration", "character_id": 1},
            ]}]},
            "character_registry": [
                {"id": 1, "name": "Narrator"},
                {"id": 2, "name": "Nastasya"},
            ],
        },
    )
    # metadata.json: the parse snapshot with the source paragraphs.
    (tmp_path / book_id / "metadata.json").write_text(json.dumps({
        "metadata": _BEATED_META,
        "content": {"chapters": [{"number": 1, "title": "Chapter One", "sections": [
            {"text": "He walked out."},
            {"text": "“Where to?” she asked."},
        ]}]},
    }))


def test_get_chapter_returns_sections_beats_and_cast(tmp_path):
    # Arrange
    _seed_beated_chapter(tmp_path)
    client = _client(tmp_path)

    # Act
    response = client.get("/books/the_gambler:fyodor_dostoyevsky/chapters/1")

    # Assert
    assert response.status_code == 200
    body = response.json()
    assert [s["text"] for s in body["sections"]] == ["He walked out.", "“Where to?” she asked."]
    assert [b["index"] for b in body["beats"]] == [0, 1, 2]
    assert body["beats"][1]["character_name"] == "Nastasya"
    assert body["beats"][1]["beat_type"] == "dialogue"
    # Cast is sorted by beat count, so the Narrator (2 beats) leads Nastasya (1).
    assert body["cast"] == [
        {"id": 1, "name": "Narrator", "count": 2},
        {"id": 2, "name": "Nastasya", "count": 1},
    ]


def test_get_chapter_serves_sections_with_no_beats_when_unbeated(tmp_path):
    # Arrange: parsed (sections in metadata.json) but not yet beated (empty book.json chapter).
    _seed_book(
        tmp_path, _BEATED_BOOK_ID,
        body={"metadata": _BEATED_META,
              "content": {"chapters": [{"number": 2, "title": "Chapter Two"}]}},
    )
    (tmp_path / _BEATED_BOOK_ID / "metadata.json").write_text(json.dumps({
        "metadata": _BEATED_META,
        "content": {"chapters": [{"number": 2, "title": "Chapter Two",
                                  "sections": [{"text": "A quiet room."}]}]},
    }))
    client = _client(tmp_path)

    # Act
    response = client.get("/books/the_gambler:fyodor_dostoyevsky/chapters/2")

    # Assert
    body = response.json()
    assert response.status_code == 200
    assert [s["text"] for s in body["sections"]] == ["A quiet room."]
    assert body["beats"] == []
    assert body["cast"] == []


def test_get_chapter_404_for_unknown_chapter(tmp_path):
    # Arrange
    _seed_beated_chapter(tmp_path)
    client = _client(tmp_path)

    # Act / Assert
    assert client.get("/books/the_gambler:fyodor_dostoyevsky/chapters/99").status_code == 404


def test_patch_beat_reassigns_speaker_and_persists(tmp_path):
    # Arrange
    _seed_beated_chapter(tmp_path)
    client = _client(tmp_path)

    # Act: reassign beat 0 from the Narrator to Nastasya.
    response = client.patch(
        "/books/the_gambler:fyodor_dostoyevsky/chapters/1/beats/0", json={"character_id": 2},
    )

    # Assert: the response and a fresh read both show the new speaker.
    assert response.status_code == 200
    assert response.json()["character_name"] == "Nastasya"
    reread = client.get("/books/the_gambler:fyodor_dostoyevsky/chapters/1").json()
    assert reread["beats"][0]["character_id"] == 2


def test_patch_beat_edits_text_and_emotion(tmp_path):
    # Arrange
    _seed_beated_chapter(tmp_path)
    client = _client(tmp_path)

    # Act
    response = client.patch(
        "/books/the_gambler:fyodor_dostoyevsky/chapters/1/beats/1",
        json={"text": "Where are you off to?", "emotion": "plain"},
    )

    # Assert
    assert response.status_code == 200
    body = response.json()
    assert body["text"] == "Where are you off to?"
    assert body["emotion"] == "plain"


def test_patch_beat_404_for_out_of_range_index(tmp_path):
    # Arrange
    _seed_beated_chapter(tmp_path)
    client = _client(tmp_path)

    # Act / Assert
    assert client.patch(
        "/books/the_gambler:fyodor_dostoyevsky/chapters/1/beats/9", json={"emotion": "x"},
    ).status_code == 404


def test_patch_beat_rejects_unknown_character(tmp_path):
    # Arrange
    _seed_beated_chapter(tmp_path)
    client = _client(tmp_path)

    # Act / Assert: id 7 is not in the registry.
    assert client.patch(
        "/books/the_gambler:fyodor_dostoyevsky/chapters/1/beats/0", json={"character_id": 7},
    ).status_code == 400


def test_get_book_runs_lists_book_runs_and_flags_stale(tmp_path):
    # Arrange: three runs for the book plus one for another book.
    store = RunStore(LocalStorage(tmp_path))
    now = datetime.now(timezone.utc)

    def _run(run_id, book_id, chapter, state, started, ended=None):
        return RunStatus(
            run_id=run_id, workflow="ai", state=state,
            params={"book_id": book_id, "start_chapter": chapter, "end_chapter": chapter},
            started_at=started.isoformat(), ended_at=ended.isoformat() if ended else None,
        )

    store.write_status(_run("r1", "the_gambler", 1, RUNNING, now))
    store.write_status(_run("r2", "the_gambler", 2, SUCCEEDED, now - timedelta(minutes=5), now))
    store.write_status(_run("r3", "the_gambler", 3, RUNNING, now - timedelta(minutes=30)))
    store.write_status(_run("r4", "other_book", 1, RUNNING, now))
    client = _client(tmp_path)

    # Act
    response = client.get("/books/the_gambler/runs")

    # Assert
    assert response.status_code == 200
    by_id = {r["run_id"]: r for r in response.json()["runs"]}
    assert set(by_id) == {"r1", "r2", "r3"}  # the other book's run is excluded
    assert by_id["r1"]["state"] == "running"
    assert by_id["r2"]["state"] == "succeeded"
    assert by_id["r3"]["state"] == "failed"  # running for 30 min past the worker cap -> stale
    assert by_id["r1"]["start_chapter"] == 1


def test_list_book_files(tmp_path):
    # Arrange
    book_dir = _seed_book(tmp_path, "the_gambler")
    (book_dir / "audio").mkdir()
    (book_dir / "audio" / "ch1.mp3").write_bytes(b"abc")
    client = _client(tmp_path)

    # Act
    response = client.get("/books/the_gambler/files")

    # Assert
    assert response.status_code == 200
    assert "audio/ch1.mp3" in response.json()["files"]


def test_serve_file_supports_range_request(tmp_path):
    # Arrange
    book_dir = _seed_book(tmp_path, "the_gambler")
    (book_dir / "audio").mkdir()
    (book_dir / "audio" / "ch1.mp3").write_bytes(b"0123456789")
    client = _client(tmp_path)

    # Act
    response = client.get(
        "/books/the_gambler/files/audio/ch1.mp3",
        headers={"Range": "bytes=2-5"},
    )

    # Assert
    assert response.status_code == 206
    assert response.content == b"2345"


def test_serve_file_rejects_traversal(tmp_path):
    # Arrange
    _seed_book(tmp_path, "the_gambler")
    (tmp_path / "secret.txt").write_text("top secret")
    client = _client(tmp_path)

    # Act
    response = client.get("/books/the_gambler/files/../secret.txt")

    # Assert
    assert response.status_code in (403, 404)


def test_serve_file_rejects_book_id_traversal(tmp_path):
    # Arrange
    _seed_book(tmp_path, "the_gambler")
    (tmp_path / "secret.txt").write_text("top secret")
    client = _client(tmp_path)

    # Act
    response = client.get("/books/%2e%2e/files/secret.txt")

    # Assert
    assert response.status_code != 200
    assert b"top secret" not in response.content


def test_start_run_rejects_non_http_url(tmp_path):
    # Arrange
    client = _client(tmp_path)

    # Act
    response = client.post(
        "/workflows/parse/runs", json={"url": "file:///etc/passwd"},
    )

    # Assert
    assert response.status_code == 400


def test_patch_voice_assignments_merges_without_dropping_keys(tmp_path):
    # Arrange
    repository = FileBookRepository(base_dir=str(tmp_path))
    book = Book(
        metadata=BookMetadata(
            title="The Gambler",
            author="Fyodor Dostoyevsky",
            releaseDate=None,
            language="en",
            originalPublication=None,
            credits=None,
        ),
        content=BookContent(chapters=[]),
        voice_assignments={1: "voice-a"},
    )
    repository.save(book)
    client = _client(tmp_path)

    # Act
    response = client.patch(
        f"/books/{book.book_id}/voice-assignments", json={"2": "voice-b"},
    )

    # Assert
    assert response.status_code == 200
    reloaded = repository.load(book.book_id)
    assert reloaded.voice_assignments == {1: "voice-a", 2: "voice-b"}
    assert reloaded.metadata.title == "The Gambler"


def test_get_logs_pages_from_cursor(tmp_path):
    # Arrange
    import time
    runner = WorkflowRunner(
        tmp_path,
        command_prefix=[sys.executable, "-c", "print('one'); print('two')"],
        cwd=tmp_path,
    )
    client = TestClient(create_app(books_dir=tmp_path, runner=runner))
    run_id = client.post(
        "/workflows/parse/runs", json={"url": "http://example/pg.zip"},
    ).json()["run_id"]
    for _ in range(200):
        if client.get(f"/runs/{run_id}").json()["state"] in ("succeeded", "failed"):
            break
        time.sleep(0.05)

    # Act
    body = client.get(f"/runs/{run_id}/logs").json()
    nxt = client.get(f"/runs/{run_id}/logs", params={"cursor": body["cursor"]}).json()

    # Assert
    assert [line.strip() for line in body["lines"]] == ["one", "two"]
    assert body["cursor"] == 2
    assert body["done"] is True
    assert nxt["lines"] == []
    assert nxt["done"] is True


def test_get_logs_unknown_run_is_404(tmp_path):
    # Arrange
    client = _client(tmp_path)

    # Act / Assert
    assert client.get("/runs/nope/logs").status_code == 404
