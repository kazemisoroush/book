"""Tests for the EvalHarness base class."""
import subprocess
from pathlib import Path

import pytest

from src.evals.eval_harness import EvalHarness


class ConcreteHarness(EvalHarness):
    """Test implementation of EvalHarness."""

    def setup(self) -> None:
        pass

    def score(self) -> None:
        pass

    def cleanup(self) -> None:
        pass


def test_run_cmd_returns_completed_process() -> None:
    """_run_cmd runs a command and returns CompletedProcess."""
    # Arrange
    harness = ConcreteHarness()

    # Act
    result = harness._run_cmd(["echo", "hello"])

    # Assert
    assert isinstance(result, subprocess.CompletedProcess)
    assert result.returncode == 0
    assert "hello" in result.stdout


def test_run_cmd_handles_timeout() -> None:
    """_run_cmd returns failed result on timeout instead of raising."""
    # Arrange
    harness = ConcreteHarness()

    # Act
    result = harness._run_cmd(["sleep", "10"], timeout=1)

    # Assert
    assert result.returncode == 1
    assert "TIMEOUT" in result.stderr


def test_git_returns_stripped_output() -> None:
    """_git runs a git command and returns stripped stdout."""
    # Arrange
    harness = ConcreteHarness()

    # Act
    result = harness._git("rev-parse --show-toplevel")

    # Assert
    assert result == "/workspaces/book"


def test_report_returns_true_when_all_pass() -> None:
    """report returns True when all recall and precision checks pass."""
    # Arrange
    harness = ConcreteHarness()
    recall = [("check1", "First check", True), ("check2", "Second check", True)]
    precision = [("check3", "Third check", True)]

    # Act
    result = harness.report(recall, precision)

    # Assert
    assert result is True


def test_report_returns_false_when_any_fail() -> None:
    """report returns False when any check fails."""
    # Arrange
    harness = ConcreteHarness()
    recall = [("check1", "First check", True), ("check2", "Second check", False)]
    precision = [("check3", "Third check", True)]

    # Act
    result = harness.report(recall, precision)

    # Assert
    assert result is False


def test_report_handles_empty_checks() -> None:
    """report handles empty check lists gracefully."""
    # Arrange
    harness = ConcreteHarness()

    # Act
    result = harness.report([], [])

    # Assert
    assert result is True


def test_state_file_returns_correct_path() -> None:
    """state_file property returns path in .claude/ directory."""
    # Arrange
    harness = ConcreteHarness()

    # Act
    path = harness.state_file

    # Assert
    assert isinstance(path, Path)
    assert path.parent.name == ".claude"
    assert "concrete_harness" in path.name
    assert path.name.endswith("_state.json")


def test_cannot_instantiate_eval_harness_directly() -> None:
    """EvalHarness cannot be instantiated without implementing abstract methods."""
    # Arrange
    # Act & Assert
    with pytest.raises(TypeError):
        EvalHarness()  # type: ignore
