"""Scorer for the Test Agent eval.

Gives the Test Agent a simple behaviour spec (clamp function) and checks
whether it wrote tests that follow all project conventions:

  1. AAA structure (# Arrange, # Act, # Assert comments)
  2. Tests actually fail (TDD red phase)
  3. Multiple tests covering happy path, edge cases, and error cases
  4. No forbidden patterns (constructor-assertion, type-check, 2+ mocks)
  5. Correct file placement and naming
  6. No implementation files modified

Usage:
    # 1. Plant the spec and clean up leftovers
    python -m src.evals.harness.score_test_agent setup

    # 2. Run the Test Agent with:
    #    "Write failing tests for the clamp function described in
    #     src/evals/harness/fixtures/planted_test_agent_spec.md.
    #     Source file: src/domain/eval_test_agent_target.py"

    # 3. Score the results
    python -m src.evals.harness.score_test_agent score

    # 4. Clean up
    python -m src.evals.harness.score_test_agent cleanup
"""
import ast
import re
from pathlib import Path

from src.evals.eval_harness import EvalHarness

SPEC_PATH = Path(__file__).parent / "fixtures" / "planted_test_agent_spec.md"


class ScoreTestAgent(EvalHarness):
    """Eval scorer for the Test Agent."""

    def __init__(self) -> None:
        super().__init__()
        self.test_path = self.repo_root / "src" / "domain" / "eval_test_agent_target_test.py"
        self.impl_path = self.repo_root / "src" / "domain" / "eval_test_agent_target.py"

    def setup(self) -> None:
        """Clean up leftovers from previous runs."""
        for path in (self.test_path, self.impl_path):
            if path.exists():
                path.unlink()
                print(f"  cleaned  {path.relative_to(self.repo_root)}")

        print(f"  spec at  {SPEC_PATH.relative_to(self.repo_root)}")
        print()
        print("Setup complete. Now run the Test Agent with a prompt like:")
        print('  "Write failing tests for the clamp function described in')
        print(f"   {SPEC_PATH.relative_to(self.repo_root)}.")
        print(f'   Source file: {self.impl_path.relative_to(self.repo_root)}"')
        print()
        print("Then: python -m src.evals.harness.score_test_agent score")

    def score(self) -> None:
        """Check if the Test Agent wrote proper failing tests."""
        recall: list[tuple[str, str, bool]] = []
        precision: list[tuple[str, str, bool]] = []

        # Recall 1: Test file exists
        test_exists = self.test_path.exists()
        recall.append(("test-file-exists", "Test file was created", test_exists))

        if not test_exists:
            self._print_report(recall, precision)
            return

        test_content = self.test_path.read_text()

        # Recall 2: AAA structure in ALL test functions
        test_tree = ast.parse(test_content)
        test_funcs = [
            node for node in ast.walk(test_tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test_")
        ]

        # Check AAA in each test function individually
        aaa_results = self._check_aaa_per_function(test_content, test_funcs)
        all_have_aaa = all(aaa_results.values()) if aaa_results else False
        tests_with_aaa = sum(1 for ok in aaa_results.values() if ok)
        total_tests = len(aaa_results)
        recall.append((
            "aaa-all-tests",
            f"ALL test functions have # Arrange / # Act / # Assert "
            f"({tests_with_aaa}/{total_tests})",
            all_have_aaa,
        ))

        # List which tests are missing AAA (for debugging)
        missing_aaa = [name for name, ok in aaa_results.items() if not ok]
        if missing_aaa:
            for name in missing_aaa[:3]:
                recall.append((
                    f"aaa-{name}",
                    f"  {name} missing AAA comments",
                    False,
                ))

        # Recall 3: Multiple test functions
        has_enough_tests = total_tests >= 4  # happy + low clamp + high clamp + error
        recall.append((
            "enough-tests",
            f"At least 4 test functions (got {total_tests})",
            has_enough_tests,
        ))

        # Recall 4: Has a happy-path test
        test_names = [f.name for f in test_funcs]
        test_names_lower = [n.lower() for n in test_names]
        has_happy = any(
            "unchanged" in n or "within" in n or "between" in n
            or "in_range" in n or "happy" in n or "returns_value" in n
            or "normal" in n or "valid" in n or "inside" in n
            for n in test_names_lower
        )
        recall.append(("has-happy-path", "Has a happy-path test", has_happy))

        # Recall 5: Has an error/exception test for low > high
        has_error_test = any(
            "raises" in n or "error" in n or "invalid" in n
            for n in test_names_lower
        )
        # Also check that pytest.raises(ValueError) appears in content
        has_value_error = "pytest.raises(ValueError)" in test_content
        recall.append((
            "has-error-test",
            "Has a ValueError test for low > high",
            has_error_test and has_value_error,
        ))

        # Recall 6: Tests actually fail (red phase)
        r = self._run_cmd(["pytest", str(self.test_path), "--no-header", "-q"], timeout=15)
        tests_fail = r.returncode != 0
        output = r.stdout + r.stderr
        # The subject module doesn't exist yet, so an ImportError or
        # ModuleNotFoundError at collection time is the EXPECTED red-phase outcome.
        subject_import_error = (
            "ModuleNotFoundError" in output
            or "ImportError" in output
            or "No module named" in output
        )
        # A proper test failure (assertion error) is also acceptable
        proper_failure = tests_fail and "FAILED" in output
        is_red = tests_fail and (subject_import_error or proper_failure)
        recall.append((
            "tests-fail",
            "Tests fail (TDD red phase confirmed)",
            is_red,
        ))

        # Recall 7: Type annotations on test functions
        has_return_annotations = all(
            f.returns is not None for f in test_funcs
        )
        recall.append((
            "type-annotations",
            "All test functions have return type annotation",
            has_return_annotations,
        ))

        # Precision 1: Implementation file NOT created
        impl_not_created = not self.impl_path.exists()
        precision.append((
            "no-impl-file",
            "Implementation file was NOT created (Test Agent doesn't write impl)",
            impl_not_created,
        ))

        # Precision 2: No constructor-assertion tests
        has_constructor_tests = self._has_constructor_assertion_pattern(test_content)
        precision.append((
            "no-constructor-tests",
            "No constructor-assertion tests",
            not has_constructor_tests,
        ))

        # Precision 3: No isinstance tests
        has_isinstance = "isinstance(" in test_content and "assert isinstance" in test_content
        precision.append((
            "no-isinstance-tests",
            "No type-check (isinstance) tests",
            not has_isinstance,
        ))

        # Precision 4: At most 1 mock per test
        max_mocks = self._max_mocks_per_test(test_content)
        precision.append((
            "max-one-mock",
            f"At most 1 mock per test (max found: {max_mocks})",
            max_mocks <= 1,
        ))

        # Precision 5: No conftest.py created
        conftest = self.repo_root / "src" / "domain" / "conftest.py"
        no_conftest = not conftest.exists()
        precision.append((
            "no-conftest",
            "No conftest.py created",
            no_conftest,
        ))

        # Precision 6: Correct file naming and placement
        correct_name = self.test_path.name == "eval_test_agent_target_test.py"
        correct_dir = self.test_path.parent.name == "domain"
        precision.append((
            "correct-placement",
            "Test file placed next to source with correct name",
            correct_name and correct_dir,
        ))

        # Precision 7: No imports from higher layers
        bad_imports = any(
            imp in test_content
            for imp in [
                "from src.ai", "from src.tts", "from src.workflows",
                "from src.parsers", "from src.cli",
            ]
        )
        precision.append((
            "no-layer-violations",
            "No imports from layers above domain",
            not bad_imports,
        ))

        self._print_report(recall, precision)

    def _check_aaa_per_function(
        self, content: str, funcs: list[ast.FunctionDef | ast.AsyncFunctionDef],
    ) -> dict[str, bool]:
        """Check if each test function has # Arrange, # Act, # Assert comments."""
        lines = content.split("\n")
        results: dict[str, bool] = {}

        for func in funcs:
            # Get the source lines for this function
            start = func.lineno - 1  # 0-indexed
            # Find end: next function or end of file
            end = func.end_lineno if func.end_lineno else len(lines)
            func_lines = "\n".join(lines[start:end])

            has_arrange = "# Arrange" in func_lines or "# arrange" in func_lines
            has_act = "# Act" in func_lines or "# act" in func_lines
            has_assert = "# Assert" in func_lines or "# assert" in func_lines

            # Exception tests using pytest.raises may merge Act+Assert — allow
            # them to have just # Arrange + # Act (with assert inside the with block)
            uses_raises = "pytest.raises" in func_lines
            if uses_raises:
                results[func.name] = has_arrange and has_act
            else:
                results[func.name] = has_arrange and has_act and has_assert

        return results

    def _has_constructor_assertion_pattern(self, content: str) -> bool:
        """Detect tests that only create an object and assert its field values.

        Splits content into per-function blocks and checks each one.
        Avoids regex backtracking on the full file.
        """
        blocks = re.split(r"\ndef test_", content)
        suspect_count = 0
        for block in blocks[1:]:  # skip preamble before first test
            lines = block.strip().split("\n")
            # Strip comment-only lines and blanks
            code_lines = [
                ln.strip() for ln in lines[1:]  # skip the def line
                if ln.strip() and not ln.strip().startswith("#")
            ]
            if len(code_lines) < 2:
                continue
            # Pattern: first code line is assignment from constructor, rest are field asserts
            has_constructor = "=" in code_lines[0] and "(" in code_lines[0]
            all_field_asserts = all(
                ln.startswith("assert ") and "." in ln for ln in code_lines[1:]
            )
            if has_constructor and all_field_asserts:
                suspect_count += 1
        return suspect_count > 2

    def _max_mocks_per_test(self, content: str) -> int:
        """Find the maximum number of mocks/patches in any single test function."""
        # Split content into test functions
        funcs = re.split(r"(?=def test_)", content)
        max_count = 0
        for func in funcs:
            mock_count = func.count("@patch") + func.count("mock.patch") + func.count("Mock(")
            max_count = max(max_count, mock_count)
        return max_count

    def _print_report(
        self,
        recall: list[tuple[str, str, bool]],
        precision: list[tuple[str, str, bool]],
    ) -> None:
        """Print the eval report."""
        print("=" * 55)
        print("TEST AGENT EVAL RESULTS")
        print("=" * 55)

        self.report(recall, precision)

    def cleanup(self) -> None:
        """Remove files created by the Test Agent."""
        for path in (self.test_path, self.impl_path):
            if path.exists():
                path.unlink()
                print(f"Removed {path}")
        # Clean conftest if created
        conftest = self.repo_root / "src" / "domain" / "conftest.py"
        if conftest.exists():
            conftest.unlink()
            print(f"Removed {conftest}")
        # Clean pycache
        cache_dir = self.test_path.parent / "__pycache__"
        if cache_dir.exists():
            for cached in cache_dir.glob("eval_test_agent_target*"):
                cached.unlink()
                print(f"Removed {cached}")
        print("Clean.")


if __name__ == "__main__":
    ScoreTestAgent().main()
