Run the full audit suite: Doc Auditor, Test Auditor, and Dead Code Remover.

$ARGUMENTS

If arguments were provided, they specify:
- A list of source files that were created or modified
- A brief summary of what changed in each file

If no arguments were provided, run in full-scan mode against the entire project.

The Audit Hook will:
1. Run the Doc Auditor — detect and fix drift between source code and documentation
2. Run the Test Auditor — audit all *_test.py files for quality rule violations
3. Run the Dead Code Remover — find and remove unused imports, functions, classes, and variables
4. Confirm the check suite (pytest + ruff + mypy) is green after all changes
5. Return a combined report from all three auditors

Use the Task tool to spawn the `audit-hook` subagent now, passing the above as its prompt.
