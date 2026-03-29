# US-013 — Cinematic Voice Casting

## Goal

When the book being processed is a well-known title with a movie or TV
adaptation, automatically cast characters using voices that match the actors
from that adaptation — sourced from ElevenLabs' public Voice Library.
A listener who loves the Harry Potter films should hear voices that evoke
Daniel Radcliffe, Emma Watson, and Alan Rickman, not generic demographic
assignments.

---

## Background / motivation

Today, voice assignment is purely demographic: match sex and age to an
available ElevenLabs voice. That works, but it is anonymous. Famous
adaptations have trained millions of listeners to hear a specific voice
_as_ a character. Casting against that expectation breaks immersion the
moment the first line of dialogue plays.

ElevenLabs' public Voice Library contains thousands of community-contributed
voices, including many that are labelled after well-known actors or described
as matching their vocal qualities. The library is searchable by name and
description via the API. This creates an opportunity: detect the book title,
retrieve the canonical movie cast, search the Voice Library for matching
voices, and use them if found — falling back to demographic matching when no
suitable match exists.

---

## Pre-implementation research required

This spec **cannot be implemented** without first completing the following
research. A research sub-task must be opened and resolved before coding begins.

### R1 — ElevenLabs Voice Library search API

Determine the exact endpoint and query parameters for searching the public
(shared) Voice Library programmatically:

- Is it `GET /v1/voices/search`, `GET /v1/shared-voices`, or something else?
- What query fields are available (name, description, category, language)?
- Does the response include a `voice_id` that can be passed directly to TTS?
- Are shared-voice `voice_id` values stable or do they rotate?
- What rate limits apply to search calls?

Primary source: ElevenLabs API docs and Python SDK source.

### R2 — Celebrity / actor voice availability

Audit what is realistically findable in the Voice Library for three test
canons: Harry Potter, The Lord of the Rings, and Pride and Prejudice (2005
film). For each character/actor pair:

- Search the library by actor name.
- Record: voice found (yes/no), voice_id, quality rating, whether it is
  an official ElevenLabs professional voice or a community contribution.
- Identify whether ElevenLabs has any officially licensed celebrity voices
  (e.g. through their partnership programme) vs community clones.

This determines whether the feature is viable before any code is written.

### R3 — Legal and ToS constraints

Review ElevenLabs' Terms of Service on community voices:

- Can an application programmatically search and use community voices in
  automated pipelines?
- Are there restrictions on commercial use of community-contributed voices
  that claim to resemble public figures?
- Document any consent / attribution requirements.

The spec cannot ship if R3 reveals a ToS violation. If community celebrity
voices are disallowed, scope narrows to **official professional voices only**,
which may make the feature impractical until ElevenLabs offers a formal
licensing path.

---

## Acceptance criteria

_These criteria are contingent on R1–R3 confirming the approach is viable._

### 1. Book recognition

A new `src/ai/book_identifier.py` module exposes:

```python
@dataclass
class AdaptationCast:
    book_title: str          # canonical title, e.g. "Harry Potter and the Philosopher's Stone"
    adaptation_title: str    # e.g. "Harry Potter and the Sorcerer's Stone (2001 film)"
    character_actor_map: dict[str, str]  # character_name → actor_name
    confidence: float        # 0.0–1.0; skip if < 0.8
```

The module calls Claude with the book title and first-chapter character list
and asks: "Is this a well-known title with a movie or TV adaptation? If so,
who played each character?" The prompt must instruct the model to return JSON
and to set `confidence < 0.8` when uncertain. No hallucination guard is
foolproof, but low confidence must trigger fallback.

### 2. Voice Library search

A new `src/tts/voice_library_search.py` module exposes:

```python
def search_actor_voice(actor_name: str, client: ElevenLabs) -> str | None:
    """Return a voice_id from the public library or None if no match."""
```

Search strategy (in order, stop at first hit):

1. Exact name match in the library (`name == actor_name`, case-insensitive).
2. Name substring match (`actor_name in voice.name`, case-insensitive).
3. Description contains the actor's full name.

If multiple matches exist, prefer: official professional voices > community
voices, then highest user rating. If no match reaches a minimum quality
threshold (to be determined from R2 findings), return `None`.

Results are cached in-process (dict keyed by actor name) to avoid repeated
API calls for the same actor across characters.

### 3. Domain model — `CastingSource` enum

Add to `src/domain/models.py`:

```python
class CastingSource(str, Enum):
    DEMOGRAPHIC  = "demographic"   # existing behaviour
    CINEMATIC    = "cinematic"     # matched to movie cast via Voice Library
```

`Character` gains `casting_source: CastingSource = CastingSource.DEMOGRAPHIC`.

### 4. Voice assignment integration

In the voice assignment step (currently in the AI workflow or TTS orchestrator):

1. Run `book_identifier` on the book title + character list.
2. If `AdaptationCast.confidence >= 0.8`, for each character in
   `character_actor_map`, call `search_actor_voice(actor_name)`.
3. If a voice_id is returned, assign it to the character and set
   `casting_source = CastingSource.CINEMATIC`.
4. Characters with no match fall through to existing demographic assignment.
5. If `AdaptationCast.confidence < 0.8` or if recognition fails, skip
   cinematic casting entirely — no partial results.

### 5. Output and observability

- `book.json` includes `casting_source` on each character.
- At synthesis time, log at `INFO` level: which book was recognised,
  which characters received cinematic voices, which fell back to demographic.
- `make verify` output includes `casting_source` values in `output.json`.

### 6. Opt-out flag

A new CLI flag `--no-cinematic-cast` disables book recognition and forces
demographic assignment. Useful for non-famous books and for testing.

### 7. Tests

- Unit test: `book_identifier` returns `confidence < 0.8` for a fictional
  unknown title (mock the AI call — 1 mock).
- Unit test: `search_actor_voice` returns `None` when the library search
  returns no results (mock the ElevenLabs client — 1 mock).
- Unit test: `Character` round-trips `casting_source` through
  `to_dict` / `from_dict`.
- Integration marker: `@pytest.mark.integration` test that calls the real
  Voice Library search for "Daniel Radcliffe" and asserts a voice_id is
  returned (skipped unless `ELEVENLABS_API_KEY` is set).

---

## Out of scope

- Voice cloning or uploading custom voice samples
- Books without any recognised movie/TV adaptation
- Narrator voice — cinematic casting applies to characters only; the narrator
  retains demographic assignment
- TV series adaptations beyond the first season's core cast
- Non-English adaptations
- Automatic quality scoring of community voices (manual curation from R2)

---

## Key design decisions

### Confidence threshold at 0.8
Book recognition via LLM is imperfect. A misidentified title would produce
absurd casting (e.g., a legal thriller narrated as if it were Star Wars).
Failing safe — falling back to demographic — is always the right call when
confidence is low. 0.8 was chosen conservatively; can be tuned after pilot.

### Search-first, don't hardcode voice IDs
Hardcoding a map of `actor_name → voice_id` creates a maintenance burden the
moment ElevenLabs removes or rotates community voices. A search-at-runtime
strategy is resilient: if the voice disappears, the search returns `None` and
demographic fallback kicks in automatically.

### Cache search results in-process
A book has at most ~20 named characters. Without caching, voice search could
make 20 API calls per book. Caching in a dict keyed by actor name reduces
this to at most one call per unique actor (some characters share actors in
ensemble casts).

### Cinematic cast is additive, not a rewrite
Existing demographic assignment is not removed. Cinematic casting sits on top
as an optional enrichment layer. Books that aren't famous, actors who aren't
in the library, and low-confidence detections all fall through cleanly.

---

## Risks and mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| ElevenLabs ToS prohibits automated use of community celebrity voices | Medium | R3 must resolve before any code is written; feature may narrow to official voices only |
| Community voice IDs rotate or are removed | High | Search-at-runtime + fallback; no hardcoded IDs |
| LLM hallucinates cast for non-famous book | Medium | Confidence threshold; opt-out flag; log all cinematic assignments |
| Actor name search returns wrong voice | Medium | Prefer official professional voices; minimum quality threshold from R2 |
| ElevenLabs adds official licensed celebrity voices (upside) | Low–Medium | Design already accommodates them via the same search path |

---

## Files expected to change

| File | Change |
|---|---|
| `src/domain/models.py` | Add `CastingSource` enum; add `casting_source` field to `Character` |
| `src/ai/book_identifier.py` | New module — LLM-based book/cast recognition |
| `src/tts/voice_library_search.py` | New module — ElevenLabs Voice Library search |
| `src/workflows/ai_project_gutenberg_workflow.py` | Wire cinematic casting into voice assignment |
| `src/main.py` | Add `--no-cinematic-cast` CLI flag |
| `src/ai/book_identifier_test.py` | New unit tests |
| `src/tts/voice_library_search_test.py` | New unit tests |
| `tests/test_cinematic_cast_integration.py` | Integration test (skipped without API key) |
