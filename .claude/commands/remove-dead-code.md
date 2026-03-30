Invoke the Dead Code Remover agent to find and remove dead code from the Python source tree.

Target path (optional, defaults to src/): $ARGUMENTS

The agent will:
1. Run ruff (F401, F811, F841) and vulture to discover dead code candidates
2. Grep-verify every candidate has zero external callers before touching anything
3. Remove confirmed dead imports, functions, classes, variables, and commented-out code
4. Run `make test && make lint` after removals to confirm nothing broke
5. Emit a structured report of everything removed, skipped, or reverted

Use the Task tool to spawn the `dead-code-remover` subagent now, passing the target path (if given) as context.
