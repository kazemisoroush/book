Invoke the Doc Updater agent to detect and fix drift between source code and documentation.

$ARGUMENTS

If no arguments were provided above, run in full-scan mode: check every .md file in the project (including AGENTS.md, CLAUDE.md, docs/, and any root-level .md files) against the current source code in src/ and fix all drift found.

If arguments were provided, they specify:
- A list of source files that were created or modified
- A brief summary of what changed in each file (new classes, new public methods, changed signatures, removed features)

The Doc Updater will:
1. Read each relevant source file and extract its public surface (module docstring, classes, functions, signatures)
2. Search all .md files and AGENTS.md / CLAUDE.md for references to changed names
3. Identify drift: stale names, stale signatures, missing entries, removed entries, stale layer claims
4. Make the minimum edits to fix confirmed drift — no rewrites, no new sections, no added prose
5. Update module-level docstrings in source files if missing or stale (the only time it touches source)
6. Emit a structured Doc Updater Report listing drift found, edits made, files checked, and files skipped

Use the Task tool to spawn the `Doc Updater` subagent now, passing the above as its prompt.
