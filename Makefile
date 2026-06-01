.PHONY: test lint verify help read narrate free best

GUTENBERG_URL   ?= https://www.gutenberg.org/cache/epub/1342/pg1342-h.zip
START_CHAPTER   ?= 1
END_CHAPTER     ?= 3
PASSAGE         ?= dracula_arrival
DEVICE          ?= cpu
DEBUG           ?=
REFRESH         ?=

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
	@echo "  make verify                            - Tests + lint + smoke test"
	@echo ""
	@echo "Options:"
	@echo "  GUTENBERG_URL=URL                      - Book URL (read/narrate)"
	@echo "  START_CHAPTER=N END_CHAPTER=M          - Chapter range (read/narrate)"
	@echo "  PASSAGE=name                           - Golden passage (free/best)"
	@echo "  DEVICE=cuda                            - PyTorch device (free)"
	@echo "  DEBUG=1                                - Keep beat files"
	@echo "  REFRESH=1                              - Bypass cache, re-run from scratch"

test:
	pytest -v

lint:
	ruff check src/
	mypy src/

verify: test lint
	python main.py --workflow ai --url $(GUTENBERG_URL) --start-chapter 1 --end-chapter 3
	@echo "Smoke test passed"

read:
	python main.py --workflow ai --url $(GUTENBERG_URL) --start-chapter $(START_CHAPTER) --end-chapter $(END_CHAPTER) $(if $(REFRESH),--refresh)

narrate:
	python main.py --workflow tts --url $(GUTENBERG_URL) --start-chapter $(START_CHAPTER) --end-chapter $(END_CHAPTER) $(if $(DEBUG),--debug)

free:
	python main.py --workflow eval-free --passage $(PASSAGE) --device $(DEVICE) $(if $(DEBUG),--debug)

best:
	python main.py --workflow eval-best --passage $(PASSAGE) $(if $(DEBUG),--debug)
