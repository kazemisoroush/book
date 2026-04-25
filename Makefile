.PHONY: test lint verify help parse ai tts ambient sfx music mix

GUTENBERG_URL   ?= https://www.gutenberg.org/cache/epub/1342/pg1342-h.zip
START_CHAPTER   ?= 1
END_CHAPTER     ?= 3

help:
	@echo "Workflows:"
	@echo "  make parse                             - Parse book structure"
	@echo "  make ai                                - AI segmentation (chapters to JSON)"
	@echo "  make tts                               - Text-to-speech synthesis"
	@echo "  make ambient                           - Generate ambient audio"
	@echo "  make sfx                               - Generate sound effects"
	@echo "  make music                             - Generate background music"
	@echo "  make mix                               - Final audio mixing"
	@echo ""
	@echo "Dev:"
	@echo "  make test                              - Run all tests"
	@echo "  make lint                              - Run ruff + mypy"
	@echo "  make verify                            - Tests + lint + AI smoke test"
	@echo ""
	@echo "Options:"
	@echo "  GUTENBERG_URL=URL                      - Book URL"
	@echo "  START_CHAPTER=N END_CHAPTER=M          - Chapter range"
	@echo ""
	@echo "All workflows run with debug=true (keep segment files)"

test:
	pytest -v

lint:
	ruff check src/
	mypy src/

verify: test lint
	python main.py --workflow ai --url $(GUTENBERG_URL) --start-chapter 1 --end-chapter 3 --debug
	@echo "Smoke test passed"

parse:
	python main.py --workflow parse --url $(GUTENBERG_URL) --start-chapter $(START_CHAPTER) --end-chapter $(END_CHAPTER) --debug

ai:
	python main.py --workflow ai --url $(GUTENBERG_URL) --start-chapter $(START_CHAPTER) --end-chapter $(END_CHAPTER) --debug

tts:
	python main.py --workflow tts --url $(GUTENBERG_URL) --start-chapter $(START_CHAPTER) --end-chapter $(END_CHAPTER) --debug

ambient:
	python main.py --workflow ambient --url $(GUTENBERG_URL) --start-chapter $(START_CHAPTER) --end-chapter $(END_CHAPTER) --debug

sfx:
	python main.py --workflow sfx --url $(GUTENBERG_URL) --start-chapter $(START_CHAPTER) --end-chapter $(END_CHAPTER) --debug

music:
	python main.py --workflow music --url $(GUTENBERG_URL) --start-chapter $(START_CHAPTER) --end-chapter $(END_CHAPTER) --debug

mix:
	python main.py --workflow mix --url $(GUTENBERG_URL) --start-chapter $(START_CHAPTER) --end-chapter $(END_CHAPTER) --debug
