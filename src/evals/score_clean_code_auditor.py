"""Scorer for the Clean Code Auditor eval.

Plants files with known violations (env var access, bare print, unseeded
random, naming convention) and one clean file. Runs the Clean Code Auditor
agent, then checks whether it detected each violation and preserved the
clean file.

Cost: $0 (no API calls — deterministic grep-based agent)

Usage:
    # 1. Plant violations
    python -m src.evals.score_clean_code_auditor setup

    # 2. Run the Clean Code Auditor agent with:
    #    "Scan src/tts/planted_*.py and src/domain/planted_*.py for violations."

    # 3. Score the results (checks agent's stdout, pasted into state file)
    python -m src.evals.score_clean_code_auditor score

    # 4. Clean up
    python -m src.evals.score_clean_code_auditor cleanup
"""
import json
import sys
from pathlib import Path

from src.evals.eval_harness import EvalHarness
from src.evals.fixtures.planted_clean_code import (
    RULE_1_CODE,
    RULE_2_CODE,
    RULE_3_CODE,
    RULE_4_CODE,
    CLEAN_CODE,
)

# Planted file locations — chosen to be in layers where violations apply
PLANTED_FILES: dict[str, tuple[Path, str]] = {
    "rule-1-env-var": (
        Path("src/tts/planted_eval_env_var.py"),
        RULE_1_CODE,
    ),
    "rule-2-bare-print": (
        Path("src/tts/planted_eval_bare_print.py"),
        RULE_2_CODE,
    ),
    "rule-3-unseeded-random": (
        Path("src/domain/planted_eval_unseeded_random.py"),
        RULE_3_CODE,
    ),
    "rule-4-naming-convention": (
        Path("src/tts/planted_eval_bad_naming.py"),
        RULE_4_CODE,
    ),
    "clean": (
        Path("src/tts/planted_eval_clean.py"),
        CLEAN_CODE,
    ),
}


class ScoreCleanCodeAuditor(EvalHarness):
    """Eval scorer for the Clean Code Auditor agent."""

    def setup(self) -> None:
        """Plant violation files and a clean file into the source tree."""
        for tag, (rel_path, code) in PLANTED_FILES.items():
            full_path = self.repo_root / rel_path
            full_path.write_text(code)
            print(f"  planted  {rel_path}  ({tag})")

        # Save state so score() knows what was planted
        state = {
            tag: str(rel_path) for tag, (rel_path, _) in PLANTED_FILES.items()
        }
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(state, indent=2))

        print()
        print("Setup complete. Now run the Clean Code Auditor agent with:")
        print('  "Scan the following files for clean-code violations:')
        for _, (rel_path, _) in PLANTED_FILES.items():
            print(f"    {rel_path}")
        print('  Report findings per rule with file paths and line numbers."')
        print()
        print("Copy the agent's report into .claude/clean_code_audit_output.txt")
        print("Then: python -m src.evals.score_clean_code_auditor score")

    def score(self) -> None:
        """Check if the agent's report mentions each planted violation."""
        # Load state
        if not self.state_file.exists():
            print("ERROR: No state file. Run setup first.")
            sys.exit(1)

        state = json.loads(self.state_file.read_text())

        # Load agent output
        output_file = self.repo_root / ".claude" / "clean_code_audit_output.txt"
        if not output_file.exists():
            print(f"ERROR: Agent output not found at {output_file}")
            print("Copy the Clean Code Auditor's report into that file.")
            sys.exit(1)

        report = output_file.read_text()

        recall_checks: list[tuple[str, str, bool]] = []
        precision_checks: list[tuple[str, str, bool]] = []

        # Recall: each violation file should be mentioned in the report
        violation_tags = [t for t in state if t != "clean"]
        for tag in violation_tags:
            rel_path = state[tag]
            filename = Path(rel_path).name
            found = filename in report or rel_path in report
            recall_checks.append((
                tag,
                f"Agent detected {tag} in {rel_path}",
                found,
            ))

        # Precision: clean file should NOT be flagged as a violation
        clean_path = state.get("clean", "")
        clean_filename = Path(clean_path).name if clean_path else ""

        # Check the report doesn't mention the clean file as a violation
        # (it may appear in "files scanned" which is OK — check it's not
        # listed under a rule heading)
        clean_not_flagged = True
        if clean_filename and clean_filename in report:
            # Check if it appears near "violation" or "Rule" context
            lines = report.split("\n")
            for i, line in enumerate(lines):
                if clean_filename in line:
                    context = "\n".join(lines[max(0, i - 2):i + 2]).lower()
                    if "violation" in context or "red flag" in context:
                        clean_not_flagged = False
                        break

        precision_checks.append((
            "clean-not-flagged",
            f"Clean file {clean_path} not flagged as violation",
            clean_not_flagged,
        ))

        # Precision: report includes all 4 rule sections
        for rule_num in range(1, 5):
            has_section = f"Rule {rule_num}" in report or f"rule {rule_num}" in report
            precision_checks.append((
                f"report-has-rule-{rule_num}",
                f"Report includes Rule {rule_num} section",
                has_section,
            ))

        passed = self.report(recall_checks, precision_checks)
        if not passed:
            sys.exit(1)

    def cleanup(self) -> None:
        """Remove planted files and state."""
        for _, (rel_path, _) in PLANTED_FILES.items():
            full_path = self.repo_root / rel_path
            if full_path.exists():
                full_path.unlink()
                print(f"  removed  {rel_path}")

        if self.state_file.exists():
            self.state_file.unlink()
            print(f"  removed  {self.state_file.relative_to(self.repo_root)}")

        output_file = self.repo_root / ".claude" / "clean_code_audit_output.txt"
        if output_file.exists():
            output_file.unlink()
            print("  removed  .claude/clean_code_audit_output.txt")

        print("Clean.")


if __name__ == "__main__":
    scorer = ScoreCleanCodeAuditor()
    scorer.main()
