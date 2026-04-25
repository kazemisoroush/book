# TD-010 — Sanitize Beat Text for TTS

## Goal

Eliminate trailing punctuation artefacts (commas, em-dashes, ellipses,
semicolons, etc.) from beat text at the point where beats are
created, so the persisted `book.json` contains clean, speech-ready text
and the TTS provider never receives text that produces audible clicks or
odd inflections.

---

## Problem

The AI section parser splits book prose into beats. Because the split
points don't always align with sentence boundaries, beats frequently
end with characters that are not natural speech terminators:

```json
{"text": "My dear Mr. Bennet,"}
{"text": "and so she went—"}
{"text": "but I never…"}
{"text": "he said; "}
```

When ElevenLabs receives text ending in a comma, semicolon, em-dash, or
ellipsis, it attempts to voice the trailing punctuation — producing
audible artefacts like an upward inflection, a click, or a swallowed
syllable. This degrades the listening experience across the entire book.

The fix belongs at the source — in the AI prompt and as a safety net in
the parser — not as a band-aid before the TTS API call.

---

## Concept

Two-layer fix:

### Layer 1: AI prompt instruction (primary)

Add an explicit rule to the prompt in `ai_section_parser.py` (around
line 421, alongside the existing "Strip quotation marks" rule):

```
- Strip trailing punctuation that is not a sentence terminator (. ! ?)
  from beat text. Commas, semicolons, colons, em-dashes, en-dashes,
  ellipses, and hyphens must not appear at the end of any beat's text.
```

This tells the LLM to produce clean beats from the start.

### Layer 2: Post-parse sanitization (safety net)

LLMs are unreliable — the prompt instruction alone is not sufficient.
Add a **pure function** `sanitize_beat_text(text: str) -> str` and
call it in `_parse_response` at beat creation time (line 621 of
`ai_section_parser.py`), right after extracting the text from the LLM
response:

```python
text = sanitize_beat_text(item.get("text", ""))
```

The function applies these rules:

1. **Strip trailing whitespace.**
2. **Strip trailing non-terminal punctuation** — remove any trailing
   characters from the set `, ; : — – - … · * # @` (and their
   Unicode variants). Repeat until the string ends with either:
   - a word character (`\w`), or
   - terminal punctuation (`. ! ? "`).
3. **Collapse internal whitespace runs** to a single space (guards
   against double-spaces that cause unnatural pauses).
4. **Strip leading whitespace.**

The function is **idempotent** — calling it twice produces the same
result as calling it once.

### Examples

| Input | Output | Why |
|---|---|---|
| `My dear Mr. Bennet,` | `My dear Mr. Bennet` | trailing comma removed |
| `and so she went—` | `and so she went` | trailing em-dash removed |
| `but I never…` | `but I never` | trailing ellipsis removed |
| `he said; ` | `he said` | trailing semicolon + space removed |
| `"Come here,"` | `"Come here,"` | comma inside closing quote — no change (quote is terminal) |
| `Hello.` | `Hello.` | period is terminal — no change |
| `What?` | `What?` | question mark is terminal — no change |
| `well—you know—` | `well—you know` | only trailing em-dash removed; internal ones untouched |

---

## Where to put it

**New file:** `src/parsers/text_sanitizer.py`

A single-purpose module with the pure function. Lives in `parsers/`
because the sanitization is part of parsing, not TTS.

**Call site:** `src/parsers/ai_section_parser.py`, in `_parse_response`,
at line 621:

```python
# Before (current):
text = item.get("text", "")

# After:
text = sanitize_beat_text(item.get("text", ""))
```

This means every beat in `book.json` is already clean. The TTS layer
receives sanitized text without needing its own fix.

---

## Acceptance criteria

1. The AI prompt includes an explicit rule to not end beat text with
   non-terminal punctuation.
2. `sanitize_beat_text` strips trailing commas, semicolons, colons,
   em-dashes, en-dashes, hyphens, ellipses, asterisks, and hash marks.
3. Terminal punctuation (`. ! ? "`) is preserved.
4. Internal punctuation (commas, dashes mid-sentence) is untouched.
5. Whitespace is normalised (leading/trailing stripped, internal runs
   collapsed).
6. The function is idempotent.
7. `sanitize_beat_text` is called in `_parse_response` on every
   beat's text field at creation time.
8. All existing tests continue to pass.
9. Unit tests in `src/parsers/text_sanitizer_test.py` cover every
   example in the table above plus edge cases (empty string,
   whitespace-only, string that is only punctuation).

---

## Out of scope

- Sanitizing at TTS synthesis time — the fix belongs at the source.
- Migrating existing cached `book.json` files — use `--reparse` to
  regenerate clean output.
- Stripping leading punctuation — beats can legitimately start with
  quotes or dashes.
- Unicode normalisation beyond the specific punctuation listed.
