"""Tests for the run-worker Lambda handler."""
import src.api.run_worker as worker
from src.api.run_store import RunStore
from src.api.run_worker import handler
from src.api.runner import FAILED, RUNNING, SUCCEEDED, RunStatus
from src.storage.local_storage import LocalStorage


def _stub_env(monkeypatch, storage) -> None:
    monkeypatch.delenv("PROVIDER_SECRET_ARN", raising=False)
    monkeypatch.setattr(worker, "configure", lambda: None)
    monkeypatch.setattr(worker, "load_provider_secret", lambda: None)
    monkeypatch.setattr(worker, "create_storage", lambda *a, **k: storage)


def test_handler_runs_the_workflow_from_the_event(tmp_path, monkeypatch):
    # Arrange
    calls = {}

    def fake_run(workflow, **kwargs):
        calls["workflow"] = workflow
        calls.update(kwargs)

    _stub_env(monkeypatch, LocalStorage(tmp_path))
    monkeypatch.setattr(worker, "run_workflow", fake_run)
    event = {
        "workflow": "ai",
        "url": "http://x/pg.zip",
        "start_chapter": 3,
        "end_chapter": 3,
        "provider": "claude-code",
    }

    # Act
    result = handler(event)

    # Assert
    assert result == {"workflow": "ai", "state": "succeeded"}
    assert calls["workflow"] == "ai"
    assert calls["url"] == "http://x/pg.zip"
    assert calls["start_chapter"] == 3
    assert calls["provider"] == "claude-code"


def test_handler_records_succeeded_status(tmp_path, monkeypatch):
    # Arrange
    storage = LocalStorage(tmp_path)
    store = RunStore(storage)
    store.write_status(RunStatus(
        run_id="r1", workflow="ai", params={}, state=RUNNING, started_at="t0",
    ))
    _stub_env(monkeypatch, storage)
    monkeypatch.setattr(worker, "run_workflow", lambda *a, **k: None)

    # Act
    result = handler({
        "run_id": "r1", "workflow": "ai", "url": "http://x/pg.zip", "start_chapter": 1,
    })

    # Assert
    assert result["state"] == SUCCEEDED
    recorded = store.read_status("r1")
    assert recorded is not None
    assert recorded.state == SUCCEEDED
    assert recorded.ended_at is not None
    assert recorded.started_at == "t0"  # preserved from the RUNNING record


def test_handler_records_failed_status_on_error(tmp_path, monkeypatch):
    # Arrange
    storage = LocalStorage(tmp_path)
    store = RunStore(storage)
    store.write_status(RunStatus(run_id="r2", workflow="ai", params={}, state=RUNNING))
    _stub_env(monkeypatch, storage)

    def boom(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(worker, "run_workflow", boom)

    # Act
    result = handler({"run_id": "r2", "workflow": "ai", "url": "http://x/pg.zip"})

    # Assert
    assert result["state"] == FAILED
    recorded = store.read_status("r2")
    assert recorded is not None and recorded.state == FAILED


def test_handler_records_failed_when_secret_load_fails(tmp_path, monkeypatch):
    # Arrange: a secret-load failure must mark the run FAILED, not leave it stuck RUNNING.
    storage = LocalStorage(tmp_path)
    store = RunStore(storage)
    store.write_status(RunStatus(run_id="r3", workflow="parse", params={}, state=RUNNING))
    _stub_env(monkeypatch, storage)

    def boom() -> None:
        raise RuntimeError("bad secret")

    monkeypatch.setattr(worker, "load_provider_secret", boom)
    monkeypatch.setattr(worker, "run_workflow", lambda *a, **k: None)

    # Act
    result = handler({"run_id": "r3", "workflow": "parse", "url": "http://x/pg.zip"})

    # Assert
    assert result["state"] == FAILED
    recorded = store.read_status("r3")
    assert recorded is not None and recorded.state == FAILED
