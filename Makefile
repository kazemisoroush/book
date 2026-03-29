.PHONY: test lint parse verify help

GUTENBERG_URL ?= https://www.gutenberg.org/cache/epub/1342/pg1342-h.zip
OUTPUT        ?= output.json
CHAPTERS      ?= 3
WORKFLOW      ?= ai

help:
	@echo "Available commands:"
	@echo "  make test                        - Run all tests with pytest"
	@echo "  make lint                        - Run ruff and mypy"
	@echo "  make verify                      - Run AI parse on 3 chapters -> output.json"
	@echo "  make parse                       - Run AI parse (use GUTENBERG_URL, OUTPUT, CHAPTERS)"
	@echo "  make parse GUTENBERG_URL=URL     - Parse a different book"
	@echo "  make parse CHAPTERS=0            - Parse all chapters"
	@echo "  make parse OUTPUT=out.json       - Write output to a specific file"
	@echo "  make parse WORKFLOW=tts          - Run full TTS pipeline"

test:
	pytest -v

lint:
	ruff check src/
	mypy src/

parse:
	python scripts/run_workflow.py --url $(GUTENBERG_URL) --output $(OUTPUT) --chapters $(CHAPTERS) --workflow $(WORKFLOW)

verify:
	python scripts/run_workflow.py --url https://www.gutenberg.org/cache/epub/1342/pg1342-h.zip --output output.json --chapters 3 --workflow ai
