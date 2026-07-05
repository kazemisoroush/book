"""Tests for the local API routes."""
import json
import sys

from fastapi.testclient import TestClient

from src.api.app import create_app
from src.api.runner import WorkflowRunner
from src.domain.models import Book, BookContent, BookMetadata
from src.repository.file_book_repository import FileBookRepository


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


def test_list_books(tmp_path):
    # Arrange
    _seed_book(tmp_path, "the_gambler")
    _seed_book(tmp_path, "dracula")
    client = _client(tmp_path)

    # Act
    response = client.get("/books")

    # Assert
    assert response.status_code == 200
    assert response.json()["books"] == ["dracula", "the_gambler"]


def test_get_book_returns_book_json(tmp_path):
    # Arrange
    _seed_book(tmp_path, "the_gambler")
    client = _client(tmp_path)

    # Act
    response = client.get("/books/the_gambler")

    # Assert
    assert response.status_code == 200
    assert response.json()["metadata"]["title"] == "The Gambler"


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
