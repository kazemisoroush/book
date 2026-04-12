"""Scorer for the Spec Writer agent eval.

Plants a rough feature request, runs the Spec Writer agent,
then checks the produced spec for structural quality.

Usage:
    python -m src.evals.harness.score_spec_writer setup
    # run the Spec Writer agent with the planted request
    python -m src.evals.harness.score_spec_writer score
    python -m src.evals.harness.score_spec_writer cleanup
"""
import json
from pathlib import Path

from src.evals.eval_harness import EvalHarness
from src.evals.fixtures.planted_spec_request import (
    EXPECTED_PREFIX,
    EXPECTED_SLUG_WORDS,
    FORBIDDEN_CONTENT,
    REQUIRED_CRITERIA_KEYWORDS,
    REQUIRED_SECTIONS,
    SPEC_REQUEST,
)


class ScoreSpecWriter(EvalHarness):
    """Eval harness for the Spec Writer agent."""

    def _specs_dir(self) -> Path:
        return self.repo_root / "docs" / "specs"

    def _find_created_spec(self) -> Path | None:
        """Find the spec file created by the agent.

        Looks for new .md files in docs/specs/ that weren't there at setup.
        """
        state = self._load_state()
        baseline_files = set(state.get("baseline_files", []))
        current_files = {
            str(p) for p in self._specs_dir().glob("*.md")
        }
        new_files = current_files - baseline_files
        # Filter to likely spec files (prefixed with us-, td-, rs-, ev-)
        spec_files = [
            Path(f) for f in new_files
            if Path(f).name.split("-")[0] in ("us", "td", "rs", "ev")
        ]
        return spec_files[0] if spec_files else None

    def _load_state(self) -> dict:
        if self.state_file.exists():
            return json.loads(self.state_file.read_text())
        return {}

    def _save_state(self, state: dict) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(state))

    def setup(self) -> None:
        """Record baseline spec files and print the request for the agent."""
        baseline_files = [
            str(p) for p in self._specs_dir().glob("*.md")
        ]
        self._save_state({"baseline_files": baseline_files})

        print("Setup complete.")
        print()
        print("Now run the Spec Writer agent with this request:")
        print("─" * 60)
        print(SPEC_REQUEST)
        print("─" * 60)
        print()
        print("Then: python -m src.evals.harness.score_spec_writer score")

    def score(self) -> None:
        """Check the produced spec against quality criteria."""
        recall: list[tuple[str, str, bool]] = []
        precision: list[tuple[str, str, bool]] = []

        # Find the created spec
        spec_path = self._find_created_spec()
        if spec_path is None:
            print("FAIL: No new spec file found in docs/specs/")
            recall.append(("file-created", "Spec file was created", False))
            self.report(recall, precision)
            return

        spec_content = spec_path.read_text()
        spec_name = spec_path.name
        spec_lower = spec_content.lower()

        print(f"Found spec: {spec_name}")
        print(f"Length: {len(spec_content)} characters")
        print()

        # --- Recall checks ---

        # 1. File was created
        recall.append(("file-created", "Spec file was created", True))

        # 2. Correct prefix
        has_prefix = spec_name.startswith(EXPECTED_PREFIX.lower() + "-")
        recall.append((
            "correct-prefix",
            f"Filename starts with {EXPECTED_PREFIX}-",
            has_prefix,
        ))

        # 3. Slug contains relevant words
        has_slug_word = any(
            word in spec_name.lower()
            for word in EXPECTED_SLUG_WORDS
        )
        recall.append((
            "relevant-slug",
            "Filename slug contains relevant keywords",
            has_slug_word,
        ))

        # 4. Required sections present
        for section in REQUIRED_SECTIONS:
            has_section = f"## {section}" in spec_content
            recall.append((
                f"section-{section.lower().replace(' ', '-')}",
                f"Has '## {section}' section",
                has_section,
            ))

        # 5. Acceptance criteria keywords
        for keyword in REQUIRED_CRITERIA_KEYWORDS:
            has_keyword = keyword.lower() in spec_lower
            recall.append((
                f"criteria-{keyword.lower().replace(' ', '-')}",
                f"Mentions '{keyword}' in acceptance criteria",
                has_keyword,
            ))

        # 6. Has numbered acceptance criteria (at least 3)
        import re
        numbered_criteria = re.findall(
            r"^\d+\.\s+", spec_content, re.MULTILINE,
        )
        has_enough_criteria = len(numbered_criteria) >= 3
        recall.append((
            "enough-criteria",
            f"Has >= 3 numbered acceptance criteria (found {len(numbered_criteria)})",
            has_enough_criteria,
        ))

        # 7. Index was updated
        index_path = self._specs_dir() / "index.md"
        index_content = index_path.read_text() if index_path.exists() else ""
        index_updated = spec_name.replace(".md", "") in index_content or spec_name in index_content
        recall.append((
            "index-updated",
            "docs/specs/index.md references the new spec",
            index_updated,
        ))

        # 8. Has a title line (# PREFIX-NNN — Title)
        has_title = bool(re.search(
            r"^#\s+(US|TD|RS|EV)-\d+\s*[—–-]\s*.+",
            spec_content,
            re.MULTILINE,
        ))
        recall.append((
            "has-title",
            "Has a properly formatted title (# PREFIX-NNN — Title)",
            has_title,
        ))

        # --- Precision checks ---

        # 1. No implementation code in the spec (outside markdown code blocks)
        # Strip code blocks before checking
        no_code_blocks = re.sub(r"```[\s\S]*?```", "", spec_content)
        for forbidden in FORBIDDEN_CONTENT:
            has_forbidden = forbidden in no_code_blocks
            precision.append((
                f"no-{forbidden.strip().replace(' ', '-')}",
                f"No '{forbidden.strip()}' outside code blocks",
                not has_forbidden,
            ))

        # 2. Spec is not too long (should be focused, not a novel)
        is_reasonable_length = len(spec_content) < 10000
        precision.append((
            "reasonable-length",
            f"Spec < 10000 chars (is {len(spec_content)})",
            is_reasonable_length,
        ))

        # 3. Doesn't duplicate existing specs
        # Check the spec doesn't reference implementing something already done
        existing_done = list((self._specs_dir() / "done").glob("*.md"))
        spec_title_words = set(spec_name.replace(".md", "").split("-")[2:])
        no_overlap = True
        for done_spec in existing_done:
            done_words = set(done_spec.name.replace(".md", "").split("-")[2:])
            if len(spec_title_words & done_words) >= 2:
                no_overlap = False
                break
        precision.append((
            "no-duplicate",
            "Doesn't duplicate an existing done spec",
            no_overlap,
        ))

        self.report(recall, precision)

    def cleanup(self) -> None:
        """Remove the created spec and revert index changes."""
        spec_path = self._find_created_spec()
        if spec_path and spec_path.exists():
            spec_path.unlink()
            print(f"Removed: {spec_path}")

        # Revert index.md changes
        self._run_cmd(["git", "checkout", "docs/specs/index.md"])
        print("Reverted docs/specs/index.md")

        # Clean up state file
        if self.state_file.exists():
            self.state_file.unlink()
            print(f"Removed state file: {self.state_file}")

        print("Cleanup complete.")


if __name__ == "__main__":
    ScoreSpecWriter().main()
