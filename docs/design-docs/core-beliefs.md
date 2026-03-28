# Core Beliefs

These are the non-negotiable principles that guide all design and implementation decisions in this project.

## 1. Test-Driven Development

**Every feature starts with a failing test.**

- Write the test first (red)
- Write minimum implementation to pass (green)
- Refactor while keeping tests green

No implementation code is written without a test that fails first. This is not optional.

## 2. SOLID Principles

- **Single Responsibility**: Each class has one reason to change
- **Open/Closed**: Extend behavior through composition, not modification
- **Liskov Substitution**: All implementations of an ABC are interchangeable
- **Interface Segregation**: Clients depend only on the methods they use
- **Dependency Inversion**: High-level modules depend on abstractions, not concrete implementations

See [DESIGN.md](../DESIGN.md) for detailed examples.

## 3. Typed Models at Boundaries

All data crossing module boundaries uses typed dataclasses with full type annotations.

No raw dictionaries in function signatures. Parse external data (HTML, JSON, env vars) into typed models at the boundary.

## 4. Fail Fast

Validate configuration and required dependencies at startup. If AWS credentials are missing, fail immediately with a clear error message — don't wait until the first API call deep in the stack.

## 5. Explicit Dependencies

Pass dependencies explicitly. No hidden global state.

- Inject `AIProvider` into `AISectionParser` constructor
- Thread `CharacterRegistry` through parsing pipeline as an explicit parameter
- Pass `Config` to components that need it

Global state (if any) must be lazy-loaded and clearly marked.

## 6. No Secrets in Source

API keys, credentials, and tokens live in environment variables only. Never hardcode secrets.

See [SECURITY.md](../SECURITY.md) for details.

## 7. Structured Logging

Use `structlog` with structured key-value pairs. Never use bare `print()` or `logging.info(str(...))`.

```python
# Good
logger.info("section_parsed", section_id=section.id, segment_count=len(segments))

# Bad
print(f"Parsed section {section.id} with {len(segments)} segments")
```

**Note**: This is a design target, not yet fully implemented.

## 8. Test-First is Non-Negotiable

This principle is so important it gets its own section.

The TDD loop is:

1. **Red** - Write a failing test that specifies the behavior
2. **Green** - Write the minimum code to pass the test
3. **Refactor** - Clean up while keeping tests green

You cannot skip step 1. If you find yourself writing implementation code without a failing test, stop and write the test first.

The agent workflow enforces this mechanically: Test Agent writes failing tests, Coder Agent implements, Orchestrator verifies.

## 9. Abstraction at Integration Points

All external dependencies (AI, downloader, TTS, file I/O) are abstracted behind interfaces (ABCs).

This makes the code testable (mock the interface) and flexible (swap implementations without touching business logic).

## 10. Determinism in Domain Models

Domain models and business logic must be deterministic and testable:

- No `datetime.now()` in domain code — pass time as a parameter or use a `Clock` abstraction
- No unseeded `random.random()` — use deterministic algorithms or pass a seed
- No file I/O in domain models — parse file content first, then pass strings/bytes to domain

Side effects belong in adapters (downloader, parsers, AI, TTS), not in domain models.

## 11. 100% Coverage on Domain Models

The domain layer is the contract. If a domain model is untested, it's undefined behavior.

All public methods on domain models must have unit tests. Coverage is mechanically enforced.

## 12. No Premature Optimization

Write the simplest code that passes the test. Optimize only when profiling shows a bottleneck.

Clarity and correctness first. Performance second.

## 13. Agent-Based Development

This project uses a multi-agent TDD workflow where agents collaborate to implement features:

- **Orchestrator** - owns a task end-to-end
- **Test Agent** - writes failing tests only
- **Coder Agent** - writes minimum implementation
- **Doc Updater** - fixes doc/code drift

The human gate sits after the Orchestrator's Completion Report. No PR is opened until the human approves.

See [AGENTS.md](../../AGENTS.md) for the full workflow.

## Why These Beliefs?

These principles exist to prevent specific failure modes:

- **TDD** prevents "works on my machine" bugs and forces testable design
- **SOLID** prevents tight coupling and fragile code
- **Typed boundaries** prevent runtime type errors and API mismatches
- **Fail fast** prevents cryptic errors deep in the stack
- **Explicit dependencies** prevents hidden state bugs
- **No secrets in source** prevents credential leaks
- **Structured logging** prevents grep-hostile logs
- **Abstraction at integration points** prevents vendor lock-in
- **Determinism in domain** prevents flaky tests
- **100% domain coverage** prevents undefined behavior
- **No premature optimization** prevents complexity for no gain

These are not just best practices — they're constraints that make the system easier to reason about, test, and change.
