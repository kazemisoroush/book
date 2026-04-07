.PHONY: test lint read narrate reparse help verify

GUTENBERG_URL   ?= https://www.gutenberg.org/cache/epub/1342/pg1342-h.zip
START_CHAPTER   ?= 1
END_CHAPTER     ?= 3
WORKFLOW        ?= ai
DEBUG           ?=

help:
	@echo "Available commands:"
	@echo "  make test                              - Run all tests with pytest"
	@echo "  make lint                              - Run ruff and mypy"
	@echo "  make verify                            - Run tests, lint, and smoke test"
	@echo "  make read                              - AI parse chapters 1-3 (cached)"
	@echo "  make narrate                           - Full TTS pipeline, chapters 1-3"
	@echo "  make read GUTENBERG_URL=URL            - Parse a different book"
	@echo "  make read START_CHAPTER=5 END_CHAPTER=10 - Parse chapters 5-10"
	@echo "  make read END_CHAPTER=0                - Parse all chapters from start"
	@echo "  make reparse                           - Force re-parse (bypass cache)"
	@echo "  make narrate DEBUG=1                   - Keep segment files alongside chapter.mp3"

test:
	pytest -v

lint:
	ruff check src/
	mypy src/

verify: test lint
	python scripts/run_workflow.py --url $(GUTENBERG_URL) --start-chapter 1 --end-chapter 3 --workflow ai
	@echo "✓ Smoke test passed"

read:
	python scripts/run_workflow.py --url $(GUTENBERG_URL) --start-chapter $(START_CHAPTER) --end-chapter $(END_CHAPTER) --workflow $(WORKFLOW)

narrate:
	python scripts/run_workflow.py --url $(GUTENBERG_URL) --start-chapter $(START_CHAPTER) --end-chapter $(END_CHAPTER) --workflow tts $(if $(DEBUG),--debug)

reparse:
	python scripts/run_workflow.py --url $(GUTENBERG_URL) --start-chapter $(START_CHAPTER) --end-chapter $(END_CHAPTER) --workflow $(WORKFLOW) --reparse
