.PHONY: test lint parse tts reparse help

GUTENBERG_URL ?= https://www.gutenberg.org/cache/epub/1342/pg1342-h.zip
CHAPTERS      ?= 3
WORKFLOW      ?= ai
DEBUG         ?=

help:
	@echo "Available commands:"
	@echo "  make test                        - Run all tests with pytest"
	@echo "  make lint                        - Run ruff and mypy"
	@echo "  make parse                       - AI parse 3 chapters (cached)"
	@echo "  make tts                         - Full TTS pipeline, 1 chapter"
	@echo "  make parse GUTENBERG_URL=URL     - Parse a different book"
	@echo "  make parse CHAPTERS=0            - Parse all chapters"
	@echo "  make reparse                     - Force re-parse (bypass cache)"
	@echo "  make tts DEBUG=1                 - Keep segment files alongside chapter.mp3"

test:
	pytest -v

lint:
	ruff check src/
	mypy src/

parse:
	python scripts/run_workflow.py --url $(GUTENBERG_URL) --chapters $(CHAPTERS) --workflow $(WORKFLOW)

tts:
	python scripts/run_workflow.py --url $(GUTENBERG_URL) --chapters 1 --workflow tts $(if $(DEBUG),--debug,)

ai:
	python scripts/run_workflow.py --url $(GUTENBERG_URL) --chapters $(CHAPTERS) --workflow $(WORKFLOW) --reparse
