"""Base class for agent eval scripts.

Provides common lifecycle (setup/score/cleanup), subprocess helpers,
git utilities, and standardized reporting.
"""
import re
import subprocess
import sys
from abc import ABC, abstractmethod
from pathlib import Path


class EvalHarness(ABC):
    """Base class for agent eval scripts.

    Subclasses must implement setup(), score(), and cleanup().
    The harness provides:
    - CLI dispatch for setup/score/cleanup commands
    - Subprocess and git helpers with timeout handling
    - Standardized report formatting for recall/precision metrics
    - State file management for persisting baseline between setup and score
    """

    def __init__(self) -> None:
        self._repo_root = Path(__file__).parent.parent.parent

    @property
    def repo_root(self) -> Path:
        """Root directory of the repository."""
        return self._repo_root

    @property
    def state_file(self) -> Path:
        """Path to JSON state file for this eval.

        Derived from class name: ScoreGitOps -> .claude/score_git_ops_state.json
        """
        # Convert CamelCase to snake_case
        class_name = self.__class__.__name__
        snake_case = re.sub(r'(?<!^)(?=[A-Z])', '_', class_name).lower()
        return self._repo_root / ".claude" / f"{snake_case}_state.json"

    def _run_cmd(
        self, cmd: list[str], timeout: int = 30,
    ) -> subprocess.CompletedProcess[str]:
        """Run a command and return the result.

        Args:
            cmd: Command as list of strings (e.g., ["ruff", "check", "file.py"])
            timeout: Timeout in seconds (default 30)

        Returns:
            CompletedProcess with stdout/stderr captured as text.
            If timeout expires, returns a failed result (returncode=1, stderr="TIMEOUT")
            instead of raising.
        """
        try:
            return subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self._repo_root,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return subprocess.CompletedProcess(
                cmd, returncode=1, stdout="", stderr="TIMEOUT",
            )

    def _git(self, cmd: str) -> str:
        """Run a git command and return stripped stdout.

        Args:
            cmd: Git command as string (e.g., "rev-parse HEAD")

        Returns:
            Stripped stdout from git command.
        """
        result = subprocess.run(
            ["git"] + cmd.split(),
            capture_output=True,
            text=True,
            cwd=self._repo_root,
        )
        return result.stdout.strip()

    def report(
        self,
        recall_checks: list[tuple[str, str, bool]],
        precision_checks: list[tuple[str, str, bool]],
    ) -> bool:
        """Print standardized eval report and return PASS/FAIL.

        Args:
            recall_checks: List of (tag, description, passed) tuples for recall
            precision_checks: List of (tag, description, passed) tuples for precision

        Returns:
            True if all checks pass (100% recall and precision), False otherwise.
        """
        total_recall = len(recall_checks)
        passed_recall = sum(1 for _, _, ok in recall_checks if ok)

        if recall_checks:
            recall_pct = passed_recall / total_recall
            print(f"\nBehaviour compliance (recall): {passed_recall}/{total_recall}")
            for tag, desc, ok in recall_checks:
                status = "PASS" if ok else "FAIL"
                print(f"  {status}  {tag}: {desc}")
        else:
            recall_pct = 1.0

        total_precision = len(precision_checks)
        passed_precision = sum(1 for _, _, ok in precision_checks if ok)

        if precision_checks:
            precision_pct = passed_precision / total_precision
            print(f"\nSafety / selectivity (precision): {passed_precision}/{total_precision}")
            for tag, desc, ok in precision_checks:
                status = "PASS" if ok else "FAIL"
                print(f"  {status}  {tag}: {desc}")
        else:
            precision_pct = 1.0

        print(f"\nRecall:    {recall_pct:.0%} ({passed_recall}/{total_recall} checks passed)")
        print(f"Precision: {precision_pct:.0%} ({passed_precision}/{total_precision} checks passed)")

        passed = recall_pct == 1.0 and precision_pct == 1.0
        print(f"Score:     {'PASS' if passed else 'FAIL'}")

        return passed

    @abstractmethod
    def setup(self) -> None:
        """Plant fixtures and record baseline state."""
        ...

    @abstractmethod
    def score(self) -> None:
        """Check results against expectations and print report."""
        ...

    @abstractmethod
    def cleanup(self) -> None:
        """Remove planted files and revert changes."""
        ...

    def main(self) -> None:
        """CLI entry point for setup/score/cleanup dispatch."""
        cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
        if cmd == "setup":
            self.setup()
        elif cmd == "score":
            self.score()
        elif cmd == "cleanup":
            self.cleanup()
        else:
            # Get the actual module name from sys.modules instead of self.__module__
            # which is __main__ when run as python -m
            main_module = sys.modules['__main__']
            if hasattr(main_module, '__spec__') and main_module.__spec__ is not None:
                module_name = main_module.__spec__.name
            else:
                module_name = self.__module__
            print(f"Usage: python -m {module_name} [setup|score|cleanup]")
