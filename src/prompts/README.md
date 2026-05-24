# Prompts

Everything related to LLM prompts: the prompt object model (which knows how to assemble itself), runner classes that build + invoke prompts that need post-processing, the static templates, and the promptfoo eval config.

## Layout

```
src/prompts/
  models/                 # AIPrompt ABC + concrete prompt dataclasses (with factory classmethods)
  builder/                # runners that build + invoke prompts and post-process the result
  templates/              # static *.prompt template files
  promptfooconfig.yaml    # promptfoo eval config (run via `make eval-prompts`)
```

## models/

Frozen dataclasses describing the input shape of a single LLM task. Each implements [`AIPrompt`](models/ai_prompt.py), splitting content into a cacheable static portion (instructions) and a per-call dynamic portion (the actual input). Providers can take advantage of prompt caching (AWS Bedrock, Anthropic) by sending the halves separately.

Where the construction logic is non-trivial (composing several registries, a context window, etc.), the prompt class exposes a `.create()` classmethod that assembles itself from the raw inputs.

- [`SectionParserPrompt`](models/section_parser_prompt.py) — the main section-parsing prompt; `SectionParserPrompt.create(text, registry, ...)` is the factory
- [`BookTitleAnnouncementPrompt`](models/book_title_prompt.py) — clean spoken-form rendering of book metadata
- [`ChapterAnnouncementPrompt`](models/chapter_announcement_prompt.py) — clean spoken-form rendering of a chapter heading

## builder/

Runners that build a prompt, call the LLM, and post-process the result. Use this layer when the "build → call → parse" flow is small enough that a dedicated class for each step would be overkill.

- [`AnnouncementFormatter`](builder/announcement_formatter.py) — builds `BookTitleAnnouncementPrompt` / `ChapterAnnouncementPrompt`, calls the LLM, and strips the result. Used by `AIWorkflow`.

For larger flows (e.g. section parsing), the parser class itself (`AISectionParser`) owns the build → call → parse loop and uses `SectionParserPrompt.create()` directly.

## templates/

Plain-text `.prompt` files. No runtime logic — they're read verbatim by the prompt classes and shared with promptfoo evals.

## promptfooconfig.yaml

Declarative eval config consumed by [promptfoo](https://www.promptfoo.dev/). Run via:

```
make eval-prompts
```
