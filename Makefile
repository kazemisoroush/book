.PHONY: test lint parse verify help

BOOK_ID  ?= 1342
OUTPUT   ?= output_$(BOOK_ID).json
CHAPTERS ?=

help:
	@echo "Available commands:"
	@echo "  make test                        - Run all tests with pytest"
	@echo "  make lint                        - Run ruff and mypy"
	@echo "  make parse                       - Run full AI parse on book 1342 (all chapters)"
	@echo "  make verify                      - Run AI parse on 3 chapters → output.json"
	@echo "  make parse BOOK_ID=74            - Run full AI parse on a different book"
	@echo "  make parse CHAPTERS=3            - Parse only the first 3 chapters"
	@echo "  make parse OUTPUT=output.json    - Write output to a specific file"

test:
	pytest -v

lint:
	ruff check src/
	mypy src/

parse:
	python scripts/parse_book.py $(BOOK_ID) $(OUTPUT) $(CHAPTERS)

verify:
	python scripts/parse_book.py 1342 output.json 3
