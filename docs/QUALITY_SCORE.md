# Quality Score

**Status**: TODO - Quality metrics to be defined

## Purpose

This document will define quality grades and scoring criteria for:

- Code quality (test coverage, type coverage, lint score)
- Documentation quality (completeness, accuracy, clarity)
- Audio quality (voice consistency, prosody, pacing)
- Parsing accuracy (speaker identification, segmentation correctness)

## Current Metrics

### Code Quality (Automated)

- **Test Coverage**: Measured by `pytest --cov`
  - Target: 100% on `domain/`
  - Current: See CI reports
- **Type Coverage**: Measured by `mypy src/`
  - Target: 100% (strict mode)
  - Current: Should pass with zero errors
- **Lint Score**: Measured by `ruff check src/`
  - Target: Zero violations
  - Current: Should pass clean

### Documentation Quality (Manual)

- **Completeness**: Are all public APIs documented?
- **Accuracy**: Does documentation match implementation?
- **Clarity**: Can a new developer understand the codebase?

Current state: Documentation has been aligned with implementation as of 2026-03-28.

### Audio Quality (Future)

Not yet defined. Will be added when TTS integration is complete.

### Parsing Accuracy (Future)

Not yet defined. Will require:

- Benchmark dataset of books with ground truth segmentation
- Metrics: speaker identification accuracy, segmentation boundary F1 score
- Comparison against human-annotated gold standard

## Future Work

Define scoring rubric for each quality dimension. Automate measurement where possible. Track quality over time.

## Related Documentation

- [DESIGN.md](DESIGN.md) - Design principles
- [core-beliefs.md](design-docs/core-beliefs.md) - Non-negotiable standards
