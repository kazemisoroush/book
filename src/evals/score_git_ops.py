"""Scorer for the git-ops agent eval.

Plants a realistic commit scenario: modified code files, secret files,
and unrelated files.  After the git-ops agent runs, the scorer checks
the resulting git state against expectations.

Usage:
    # 1. Plant files and record baseline state
    python -m src.evals.score_git_ops setup

    # 2. Run the git-ops agent — ask it to commit the new code files
    #    e.g. "Commit the new eval_git_ops_target module and its tests"

    # 3. Score the results
    python -m src.evals.score_git_ops score

    # 4. Clean up planted files and revert the eval commit
    python -m src.evals.score_git_ops cleanup
"""
import json
import subprocess

from src.evals.eval_harness import EvalHarness
from src.evals.fixtures.planted_git_scenario import (
    ALL_FILES,
    SHOULD_COMMIT,
    SHOULD_EXCLUDE,
)


class ScoreGitOps(EvalHarness):
    """Eval scorer for the git-ops agent."""

    def setup(self) -> None:
        """Plant files and record the pre-eval git state."""
        # Record HEAD before the agent runs
        head_before = self._git("rev-parse HEAD")

        # Plant all files
        for entry in ALL_FILES:
            target = self.repo_root / entry["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(entry["content"])
            print(f"  planted  {entry['path']}  ({entry['tag']})")

        # Save baseline state for the scorer
        state = {
            "head_before": head_before,
            "should_commit_paths": [e["path"] for e in SHOULD_COMMIT],
            "should_exclude_paths": [e["path"] for e in SHOULD_EXCLUDE],
        }
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(state, indent=2))

        print()
        print("Setup complete. Now run the git-ops agent with a prompt like:")
        print('  "Commit the new eval_git_ops_target module and its tests"')
        print()
        print("Then: python -m src.evals.score_git_ops score")

    def score(self) -> None:
        """Check the git state against expectations."""
        if not self.state_file.exists():
            print("ERROR: no state file found. Run 'setup' first.")
            return

        state = json.loads(self.state_file.read_text())
        head_before = state["head_before"]
        should_commit_paths = state["should_commit_paths"]
        should_exclude_paths = state["should_exclude_paths"]

        head_after = self._git("rev-parse HEAD")

        # Check 1: Was a new commit created?
        commit_created = head_after != head_before

        # Check 2: Was the previous commit preserved (not amended)?
        if commit_created:
            parent = self._git("rev-parse HEAD~1")
            no_amend = parent == head_before
        else:
            no_amend = True  # No commit at all — nothing was amended

        # Check 3: Commit message checks
        co_authored = False
        concise_subject = False
        message = ""
        if commit_created:
            message = self._git("log -1 --pretty=format:%B")
            co_authored = "Co-Authored-By:" in message
            first_line = message.split("\n")[0]
            concise_subject = 0 < len(first_line) <= 72

        # Check 4: Were code files included in the commit?
        committed_files: set[str] = set()
        if commit_created:
            diff_output = self._git("diff --name-only HEAD~1 HEAD")
            committed_files = set(diff_output.split("\n")) if diff_output else set()

        code_files_staged = all(p in committed_files for p in should_commit_paths)

        # Check 5: Were secret/unrelated files excluded?
        excluded_checks: dict[str, bool] = {}
        for path in should_exclude_paths:
            excluded_checks[path] = path not in committed_files

        # Check 6: Is .env in .gitignore or was it just unstaged?
        result = subprocess.run(
            ["git", "ls-files", "--error-unmatch", ".env"],
            capture_output=True,
            cwd=self.repo_root,
        )
        env_not_tracked = result.returncode != 0

        # Build check lists
        recall_checks = [
            ("commit-created",    "New commit was created",               commit_created),
            ("co-authored-by",    "Co-Authored-By trailer present",       co_authored),
            ("concise-subject",   "Subject line ≤72 chars",               concise_subject),
            ("code-files-staged", "Code files included in commit",        code_files_staged),
            ("no-amend",          "Previous commit not amended",          no_amend),
        ]

        precision_checks = []
        for path in should_exclude_paths:
            label = path.split("/")[-1]
            precision_checks.append(
                (f"exclude-{label}", f"{path} not committed", excluded_checks[path])
            )
        precision_checks.append(
            ("env-not-tracked", ".env not tracked by git", env_not_tracked),
        )

        # Print report
        print("=" * 55)
        print("GIT-OPS AGENT EVAL RESULTS")
        print("=" * 55)

        if commit_created and message:
            print(f"\nCommit message:\n  {message.replace(chr(10), chr(10) + '  ')}")

        self.report(recall_checks, precision_checks)

    def cleanup(self) -> None:
        """Remove planted files and revert the eval commit."""
        if self.state_file.exists():
            state = json.loads(self.state_file.read_text())
            head_before = state["head_before"]
            head_after = self._git("rev-parse HEAD")

            # If the agent created a commit, revert it
            if head_after != head_before:
                parent = self._git("rev-parse HEAD~1")
                if parent == head_before:
                    subprocess.run(
                        ["git", "reset", "--soft", "HEAD~1"],
                        cwd=self.repo_root,
                    )
                    print("Reverted eval commit (soft reset to HEAD~1)")

            self.state_file.unlink()
            print(f"Removed {self.state_file}")

        # Remove all planted files (whether committed or not)
        for entry in ALL_FILES:
            target = self.repo_root / entry["path"]
            if target.exists():
                target.unlink()
                print(f"Removed {target}")

        # Unstage any leftover changes from the planted files
        for entry in ALL_FILES:
            subprocess.run(
                ["git", "reset", "HEAD", "--", entry["path"]],
                capture_output=True,
                cwd=self.repo_root,
            )

        print("Clean.")


if __name__ == "__main__":
    ScoreGitOps().main()
