# Prompts

Everything related to LLM prompts: the prompt object model, the builders that assemble them, the static templates they render from, and the promptfoo eval config that exercises them.

## Layout

```
src/prompts/
  models/                 # AIPrompt ABC + concrete prompt dataclasses
  builder/                # builders that assemble prompts (and run them)
  templates/              # static *.prompt template files
  promptfooconfig.yaml    # promptfoo eval config (run via `make eval-prompts`)
```

## models/

Frozen dataclasses that describe the input shape of a single LLM task. Each implements [`AIPrompt`](models/ai_prompt.py), splitting content into a cacheable static portion (instructions) and a per-call dynamic portion (the actual input). Providers can take advantage of prompt caching (AWS Bedrock, Anthropic) by sending the halves separately.

- [`SectionParserPrompt`](models/section_parser_prompt.py) — the main section-parsing prompt
- [`BookTitleAnnouncementPrompt`](models/book_title_prompt.py) — clean spoken-form rendering of book metadata
- [`ChapterAnnouncementPrompt`](models/chapter_announcement_prompt.py) — clean spoken-form rendering of a chapter heading

## builder/

Classes that assemble (and, for the smaller ones, also run) prompts. The two builders here render their static instructions from files in [`templates/`](templates/) so the application and promptfoo evals share a single source of truth.

- [`PromptBuilder`](builder/prompt_builder.py) — builds `SectionParserPrompt` from the current registries, surrounding context, and the section text. Used by `AISectionParser`.
- [`AnnouncementFormatter`](builder/announcement_formatter.py) — builds `BookTitleAnnouncementPrompt` / `ChapterAnnouncementPrompt`, calls the LLM, and post-processes the result. Used by `AIWorkflow`.

## templates/

Plain-text `.prompt` files. No runtime logic — `{{ var_name }}` placeholders are substituted by the builders at render time.

## promptfooconfig.yaml

Declarative eval config consumed by [promptfoo](https://www.promptfoo.dev/). Run via:

```
make eval-prompts
```
