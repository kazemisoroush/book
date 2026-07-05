.PHONY: test lint help read narrate eval serve openapi web-install web-dev web-build web-test infra-synth

GUTENBERG_URL   ?= https://www.gutenberg.org/cache/epub/1342/pg1342-h.zip
START_CHAPTER   ?= 1
END_CHAPTER     ?= 3
DEBUG           ?=
REFRESH         ?=
ID              ?=

help:
	@echo "Workflows:"
	@echo "  make read                              - AI parse chapters (cached)"
	@echo "  make narrate                           - Full TTS pipeline (Fish Audio + Stable Audio)"
	@echo "  make serve                             - Run the thin local API (remote control over the CLI)"
	@echo ""
	@echo "Studio (web):"
	@echo "  make openapi                           - Export openapi.yaml from the API (the FE contract)"
	@echo "  make web-install                       - Install frontend dependencies"
	@echo "  make web-dev                           - Run the studio UI dev server"
	@echo "  make web-build                         - Build the studio UI static site"
	@echo "  make infra-synth                       - Synthesize the CDK infra (cdk-nag gate)"
	@echo ""
	@echo "Dev:"
	@echo "  make test                              - Run all tests"
	@echo "  make lint                              - Run ruff + mypy"
	@echo "  make eval [ID=NN]                      - Run chapter_parser eval (all cases or one)"
	@echo ""
	@echo "Options:"
	@echo "  GUTENBERG_URL=URL                      - Book URL (read/narrate)"
	@echo "  START_CHAPTER=N END_CHAPTER=M          - Chapter range (read/narrate)"
	@echo "  DEBUG=1                                - Keep beat files"
	@echo "  REFRESH=1                              - Bypass cache, re-run from scratch"
	@echo "  ID=NN                                  - Eval case id (eval)"

test:
	pytest -v

lint:
	ruff check src/
	mypy src/

read:
	python main.py --workflow ai --url $(GUTENBERG_URL) --start-chapter $(START_CHAPTER) --end-chapter $(END_CHAPTER) $(if $(REFRESH),--refresh)

narrate:
	python main.py --workflow tts --url $(GUTENBERG_URL) --start-chapter $(START_CHAPTER) --end-chapter $(END_CHAPTER) $(if $(DEBUG),--debug)

eval:
	PYTHONPATH=. python evals/chapter_parser/run.py $(if $(ID),--case $(ID))

serve:
	python -m src.api

openapi:
	PYTHONPATH=. python scripts/export_openapi.py

web-install:
	cd frontend && npm ci

web-dev:
	cd frontend && npm run dev

web-build:
	cd frontend && npm run build

web-test:
	cd frontend && npm run test

infra-synth:
	cd infra && cdk synth --quiet
