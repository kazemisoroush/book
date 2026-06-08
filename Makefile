.PHONY: test lint help read narrate free best eval

GUTENBERG_URL   ?= https://www.gutenberg.org/cache/epub/1342/pg1342-h.zip
START_CHAPTER   ?= 1
END_CHAPTER     ?= 3
PASSAGE         ?= dracula_arrival
DEVICE          ?= cpu
DEBUG           ?=
REFRESH         ?=
ID              ?=

help:
	@echo "Workflows:"
	@echo "  make read                              - AI parse chapters (cached)"
	@echo "  make narrate                           - Full TTS pipeline (Fish Audio + Stable Audio)"
	@echo "  make free                              - Eval: VibeVoice + AudioCraft (free, local)"
	@echo "  make best                              - Eval: Fish Audio + Stable Audio (paid, best quality)"
	@echo ""
	@echo "Dev:"
	@echo "  make test                              - Run all tests"
	@echo "  make lint                              - Run ruff + mypy"
	@echo "  make eval [ID=NN]                      - Run chapter_parser eval (all cases or one)"
	@echo ""
	@echo "Options:"
	@echo "  GUTENBERG_URL=URL                      - Book URL (read/narrate)"
	@echo "  START_CHAPTER=N END_CHAPTER=M          - Chapter range (read/narrate)"
	@echo "  PASSAGE=name                           - Golden passage (free/best)"
	@echo "  DEVICE=cuda                            - PyTorch device (free)"
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

free:
	python main.py --workflow eval-free --passage $(PASSAGE) --device $(DEVICE) $(if $(DEBUG),--debug)

best:
	python main.py --workflow eval-best --passage $(PASSAGE) $(if $(DEBUG),--debug)

eval:
	PYTHONPATH=. python evals/chapter_parser/run.py $(if $(ID),--case $(ID))
