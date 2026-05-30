# Prompts

Everything related to LLM prompts: the prompt object model (each class owns its own template file), runner classes that build, invoke, and post-process prompts, the static templates, and the promptfoo eval config.

## Layout

```
src/prompts/
  models/                 # AIPrompt ABC and concrete prompt dataclasses (each owns its .prompt template)
  runners/                # classes that build a prompt, call the LLM, and post-process the result
  templates/              # static *.prompt template files
  promptfooconfig.yaml    # promptfoo eval config (run via `make eval-prompts`)
```

## models/

Frozen dataclasses describing the input shape of a single LLM task. Each implements [`AIPrompt`](models/ai_prompt.py) and declares the template file it owns via a `TEMPLATE_FILENAME` class attribute, loaded at module import from [templates/](templates/). The class splits its content into a cacheable static portion (instructions) and a per-call dynamic portion (the actual input). Providers can take advantage of prompt caching (AWS Bedrock, Anthropic) by sending the halves separately.

Callers never inject the template text. Where the construction logic is non-trivial (composing several registries, a context window, etc.), the prompt class exposes a `.create()` classmethod that assembles itself from the raw inputs.

- [`SectionParserPrompt`](models/section_parser_prompt.py) is the main section-parsing prompt; `SectionParserPrompt.create(text, registry, ...)` is the factory. Template: [`section_parser.prompt`](templates/section_parser.prompt).
- [`BookTitleAnnouncementPrompt`](models/book_title_prompt.py) renders book metadata into clean spoken form. Template: [`book_title.prompt`](templates/book_title.prompt).
- [`ChapterAnnouncementPrompt`](models/chapter_announcement_prompt.py) renders a chapter heading into clean spoken form. Template: [`chapter_announcement.prompt`](templates/chapter_announcement.prompt).

## runners/

Classes that build a prompt, call the LLM, and post-process the result. Use this layer when the build, call, and parse flow is small enough that a dedicated class per step would be overkill.

- [`AnnouncementFormatter`](runners/announcement_formatter.py) builds `BookTitleAnnouncementPrompt` and `ChapterAnnouncementPrompt`, calls the LLM, and strips the result. Used by [`AIWorkflow`](../workflows/ai_workflow.py).

For larger flows (for example section parsing), the parser class itself ([`AISectionParser`](../parsers/ai_section_parser.py)) owns the build, call, and parse loop and uses `SectionParserPrompt.create()` directly.

## templates/

Plain-text `.prompt` files. No runtime logic; each file is read verbatim by its owning prompt class and shared with promptfoo evals.

## promptfooconfig.yaml

Declarative eval config consumed by [promptfoo](https://www.promptfoo.dev/). Run via:

```
make eval-prompts
```
