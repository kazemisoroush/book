Invoke the Orchestrator agent to own the following task end-to-end:

$ARGUMENTS

The Orchestrator will:
1. Read and understand the ExecPlan (if a path was given) or synthesise one from the description
2. Confirm acceptance criteria with you before any implementation
3. Drive the Test Agent → Coder Agent TDD loop for each step
4. Run full verification (make test, make lint) before finishing
5. Hand off to Doc Updater if public interfaces changed
6. Emit a structured Completion Report

Use the Task tool to spawn the `orchestrator` subagent now, passing the task above as its prompt.
