.PHONY: test lint parse help

BOOK_ID ?= 1342
OUTPUT   ?= output_$(BOOK_ID).json

help:
	@echo "Available commands:"
	@echo "  make test              - Run all tests with pytest"
	@echo "  make lint              - Run ruff and mypy"
	@echo "  make parse             - Run full AI parse on book 1342 (Pride and Prejudice)"
	@echo "  make parse BOOK_ID=74  - Run full AI parse on a different book"

test:
	pytest -v

lint:
	ruff check src/
	mypy src/

parse:
	python scripts/parse_book.py $(BOOK_ID) $(OUTPUT)
