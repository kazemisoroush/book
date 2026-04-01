.PHONY: test lint parse verify reparse help

GUTENBERG_URL ?= https://www.gutenberg.org/cache/epub/1342/pg1342-h.zip
CHAPTERS      ?= 1
WORKFLOW      ?= ai

help:
	@echo "Available commands:"
	@echo "  make test                        - Run all tests with pytest"
	@echo "  make lint                        - Run ruff and mypy"
	@echo "  make verify                      - Run parse with defaults (cached)"
	@echo "  make parse                       - Run AI parse (use GUTENBERG_URL, CHAPTERS)"
	@echo "  make parse GUTENBERG_URL=URL     - Parse a different book"
	@echo "  make parse CHAPTERS=0            - Parse all chapters"
	@echo "  make parse WORKFLOW=tts          - Run full TTS pipeline"
	@echo "  make reparse                     - Force re-parse (bypass cache)"

test:
	pytest -v

lint:
	ruff check src/
	mypy src/

parse:
	python scripts/run_workflow.py --url $(GUTENBERG_URL) --chapters $(CHAPTERS) --workflow $(WORKFLOW)

verify: parse

reparse:
	python scripts/run_workflow.py --url $(GUTENBERG_URL) --chapters $(CHAPTERS) --workflow $(WORKFLOW) --reparse
