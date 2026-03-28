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

## 8. Abstraction at Integration Points

All external dependencies (AI, downloader, TTS, file I/O) are abstracted behind interfaces (ABCs).

This makes the code testable (mock the interface) and flexible (swap implementations without touching business logic).

## 9. Determinism in Domain Models

Domain models and business logic must be deterministic and testable:

- No `datetime.now()` in domain code — pass time as a parameter or use a `Clock` abstraction
- No unseeded `random.random()` — use deterministic algorithms or pass a seed
- No file I/O in domain models — parse file content first, then pass strings/bytes to domain

Side effects belong in adapters (downloader, parsers, AI, TTS), not in domain models.

## 10. 100% Coverage on Domain Models

The domain layer is the contract. If a domain model is untested, it's undefined behavior.

All public methods on domain models must have unit tests. Coverage is mechanically enforced.

## 11. No Premature Optimization

Write the simplest code that passes the test. Optimize only when profiling shows a bottleneck.

Clarity and correctness first. Performance second.

## 12. Agent-Based Development

See [AGENTS.md](../../AGENTS.md). Human gate sits after the Orchestrator's Completion Report.
