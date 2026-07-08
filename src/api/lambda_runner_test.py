"""Tests for the Lambda-dispatch workflow runner."""
import json
from typing import Any

from src.api.lambda_runner import LambdaWorkflowRunner
from src.api.runner import RUNNING, RunParams
from src.storage.local_storage import LocalStorage


class _FakeLambda:
    """Records invoke calls instead of hitting AWS."""

    def __init__(self) -> None:
        self.invocations: list[dict[str, Any]] = []

    def invoke(self, FunctionName: str, InvocationType: str, Payload: bytes) -> dict[str, int]:  # noqa: N803
        self.invocations.append({
            "name": FunctionName,
            "type": InvocationType,
            "payload": json.loads(Payload),
        })
        return {"StatusCode": 202}


def test_start_records_running_and_invokes_worker(tmp_path) -> None:
    # Arrange
    storage = LocalStorage(tmp_path)
    fake = _FakeLambda()
    runner = LambdaWorkflowRunner("book-worker", storage, client=fake)

    # Act
    status = runner.start("ai", RunParams(url="http://x/pg.zip", start_chapter=3, end_chapter=3))

    # Assert: RUNNING recorded and readable back
    assert status.state == RUNNING
    reread = runner.status(status.run_id)
    assert reread is not None and reread.state == RUNNING
    # worker invoked asynchronously with the run details
    assert len(fake.invocations) == 1
    invocation = fake.invocations[0]
    assert invocation["name"] == "book-worker"
    assert invocation["type"] == "Event"
    assert invocation["payload"]["run_id"] == status.run_id
    assert invocation["payload"]["workflow"] == "ai"
    assert invocation["payload"]["url"] == "http://x/pg.zip"
    assert invocation["payload"]["start_chapter"] == 3


def test_status_of_unknown_run_is_none(tmp_path) -> None:
    # Arrange
    runner = LambdaWorkflowRunner("book-worker", LocalStorage(tmp_path), client=_FakeLambda())

    # Act / Assert
    assert runner.status("nope") is None


def test_cloud_logs_are_empty_for_now(tmp_path) -> None:
    # Arrange
    runner = LambdaWorkflowRunner("book-worker", LocalStorage(tmp_path), client=_FakeLambda())

    # Act / Assert
    assert runner.read_logs("any", cursor=0) == ([], 0)
