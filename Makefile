.PHONY: test lint parse tts reparse help verify

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
	@echo "  make parse                             - AI parse chapters 1-3 (cached)"
	@echo "  make tts                               - Full TTS pipeline, chapters 1-1"
	@echo "  make parse GUTENBERG_URL=URL           - Parse a different book"
	@echo "  make parse START_CHAPTER=5 END_CHAPTER=10 - Parse chapters 5-10"
	@echo "  make parse END_CHAPTER=0               - Parse all chapters from start"
	@echo "  make reparse                           - Force re-parse (bypass cache)"
	@echo "  make tts DEBUG=1                       - Keep segment files alongside chapter.mp3"

test:
	pytest -v

lint:
	ruff check src/
	mypy src/

verify: test lint
	python scripts/run_workflow.py --url $(GUTENBERG_URL) --start-chapter 1 --end-chapter 3 --workflow ai
	@echo "✓ Smoke test passed"

parse:
	python scripts/run_workflow.py --url $(GUTENBERG_URL) --start-chapter $(START_CHAPTER) --end-chapter $(END_CHAPTER) --workflow $(WORKFLOW)

tts:
	python scripts/run_workflow.py --url $(GUTENBERG_URL) --start-chapter 1 --end-chapter 1 --workflow tts --debug

reparse:
	python scripts/run_workflow.py --url $(GUTENBERG_URL) --start-chapter $(START_CHAPTER) --end-chapter $(END_CHAPTER) --workflow $(WORKFLOW) --reparse
