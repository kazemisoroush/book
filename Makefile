.PHONY: test lint help

help:
	@echo "Available commands:"
	@echo "  make test  - Run all tests with pytest"
	@echo "  make lint  - Run flake8 linter on source code"

test:
	python3 -m pytest src/ -v

lint:
	python3 -m flake8 src/ main.py --max-line-length=120 --exclude=__pycache__
