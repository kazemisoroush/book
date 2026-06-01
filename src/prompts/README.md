# Prompts

LLM prompt templates plus the fluent builders that render them.

## Layout

```
src/prompts/
  prompt_builder.py                          # PromptBuilder ABC
  chapter_parser/
    chapter_parser.prompt                    # template ({{ INPUT_* }} placeholders)
    chapter_parser_prompt_builder.py         # ChapterParserPromptBuilder
    input.py                                 # PromptInput + nested input models
    output.py                                # PromptOutput + nested output models
```

## PromptBuilder

[`PromptBuilder`](prompt_builder.py) is a minimal ABC with one method: `build() -> str`. Concrete subclasses are frozen dataclasses that expose typed `.with_*()` setters for each input slot. Setters return a new builder so chains stay immutable; `build()` renders the template and returns the final prompt string.

## Per-prompt folder

Each prompt owns one folder containing its `.prompt` template, its builder, and the typed input/output models exchanged with the LLM. To add a new prompt, create a sibling folder mirroring `chapter_parser/`.

## Typed I/O models

Every prompt has matching `input.py` and `output.py` modules with frozen dataclasses describing exactly what gets serialised into the prompt and what gets parsed back out. Builders accept the typed input; callers parse the JSON response via `PromptOutput.from_dict(...)`. Callers never hand-roll dicts.

## Example

```python
from src.prompts.chapter_parser.chapter_parser_prompt_builder import (
    ChapterParserPromptBuilder,
)
from src.prompts.chapter_parser.input import (
    PromptInput, PromptInputChapter, PromptInputMetadata, PromptInputSection,
)
from src.prompts.chapter_parser.output import PromptOutput

prompt_input = PromptInput(
    metadata=PromptInputMetadata(title="...", author="..."),
    chapters=[PromptInputChapter(id=1, sections=[PromptInputSection(id=1, text="...", type="text")])],
)
prompt: str = (
    ChapterParserPromptBuilder()
    .with_chapter(prompt_input)
    .with_allowed_beat_types(["narration", "dialogue"])
    .build()
)
response = PromptOutput.from_dict(json.loads(raw_llm_response))
```
