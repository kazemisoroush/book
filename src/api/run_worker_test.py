"""Tests for the run-worker Lambda handler."""
import src.api.run_worker as worker
from src.api.run_worker import handler


def test_handler_runs_the_workflow_from_the_event(monkeypatch):
    # Arrange
    calls = {}

    def fake_run(workflow, **kwargs):
        calls["workflow"] = workflow
        calls.update(kwargs)

    monkeypatch.setattr(worker, "run_workflow", fake_run)
    monkeypatch.setattr(worker, "configure", lambda: None)
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
