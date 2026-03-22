.PHONY: test lint help

help:
	@echo "Available commands:"
	@echo "  make test  - Run all tests with pytest"
	@echo "  make lint  - Run ruff and mypy"

test:
	pytest -v

lint:
	ruff check src/
	mypy src/
