"""Tests for the subprocess-backed workflow runner."""
import sys
import time

from src.api.runner import FAILED, RUNNING, SUCCEEDED, RunParams, WorkflowRunner


def _wait_terminal(runner, run_id, timeout=10.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = runner.status(run_id)
        if status is not None and status.state in (SUCCEEDED, FAILED):
            return status
        time.sleep(0.05)
    raise AssertionError("run did not finish in time")


def _runner(tmp_path, code):
    prefix = [sys.executable, "-c", code]
    return WorkflowRunner(tmp_path, command_prefix=prefix, cwd=tmp_path)


def test_start_records_running_status(tmp_path):
    # Arrange
    runner = _runner(tmp_path, "import time; time.sleep(0.5)")

    # Act
    status = runner.start("ai", RunParams(url="http://example/pg.zip"))

    # Assert
    assert status.state == RUNNING
    assert status.pid is not None
    assert runner.status(status.run_id).state == RUNNING


def test_successful_run_finalizes_as_succeeded(tmp_path):
    # Arrange
    runner = _runner(tmp_path, "print('done')")

    # Act
    status = runner.start("parse", RunParams(url="http://example/pg.zip"))
    final = _wait_terminal(runner, status.run_id)

    # Assert
    assert final.state == SUCCEEDED
    assert final.returncode == 0
    assert final.ended_at is not None


def test_failing_run_finalizes_as_failed(tmp_path):
    # Arrange
    runner = _runner(tmp_path, "import sys; sys.exit(3)")

    # Act
    status = runner.start("ai", RunParams(url="http://example/pg.zip"))
    final = _wait_terminal(runner, status.run_id)

    # Assert
    assert final.state == FAILED
    assert final.returncode == 3


def test_tail_streams_log_lines_until_terminal(tmp_path):
    # Arrange
    code = "print('line-1'); print('line-2')"
    runner = _runner(tmp_path, code)

    # Act
    status = runner.start("parse", RunParams(url="http://example/pg.zip"))
    lines = "".join(runner.tail(status.run_id))

    # Assert
    assert "line-1" in lines
    assert "line-2" in lines


def test_tail_yields_terminal_lines_individually(tmp_path):
    # Arrange
    code = "print('a'); print('b'); print('c')"
    runner = _runner(tmp_path, code)

    # Act
    status = runner.start("parse", RunParams(url="http://example/pg.zip"))
    _wait_terminal(runner, status.run_id)
    chunks = list(runner.tail(status.run_id))

    # Assert
    assert [c.strip() for c in chunks if c.strip()] == ["a", "b", "c"]
    assert all(chunk.count("\n") <= 1 for chunk in chunks)


def test_status_is_none_for_unknown_run(tmp_path):
    # Arrange
    runner = _runner(tmp_path, "print('x')")

    # Act
    status = runner.status("does-not-exist")

    # Assert
    assert status is None
