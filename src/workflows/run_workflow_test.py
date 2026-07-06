"""Tests for the shared run_workflow helper."""
from unittest.mock import MagicMock

import src.workflows.run_workflow as run_module
from src.workflows.run_workflow import run_workflow


def test_run_workflow_builds_the_workflow_and_runs_the_range(monkeypatch):
    # Arrange
    workflow = MagicMock()
    created = {}

    def fake_create(name, provider=None):
        created["name"] = name
        created["provider"] = provider
        return workflow

    monkeypatch.setattr(run_module, "create_workflow", fake_create)

    # Act
    run_workflow(
        "ai", url="http://x/pg.zip", start_chapter=2, end_chapter=3,
        provider="claude-code",
    )

    # Assert
    assert created == {"name": "ai", "provider": "claude-code"}
    request = workflow.run.call_args.args[0]
    assert request.url == "http://x/pg.zip"
    assert request.start_chapter == 2
    assert request.end_chapter == 3
