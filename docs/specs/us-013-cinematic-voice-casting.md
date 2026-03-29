# US-013 — Cinematic Voice Casting

## Goal

When the book being processed is a well-known title with a movie or TV
adaptation, identify the canonical film cast and use each actor's known
vocal profile (gender, age, accent) to select high-quality ElevenLabs
voices that match each character — rather than generic demographic
assignment. A listener who knows the Harry Potter films should hear voices
that *feel like* the cast, even if they are not literally the actors.

> **Stretch goal:** if ElevenLabs adds a programmatic API to the Iconic
> Marketplace (their licensed-celebrity-voice programme), Phase 2 upgrades
> this to actual actor voice matching. See Phase 2 note at the end.

---

## Research findings (R1–R3 resolved 2026-03-29)

Report: [`docs/specs/done/rs-001-cinematic-voice-casting.md`](done/rs-001-cinematic-voice-casting.md)

### R1 — API confirmed (GREEN)

- Endpoint: `GET /v1/shared-voices`; SDK: `client.voices.get_shared(...)`
- Accepts `search`, `gender`, `age`, `accent`, `category`, `language`,
  `page_size`, and more
- Response includes `voice_id` directly usable in TTS synthesis — no
  separate "add to account" step required
- `voice_id` values are stable at runtime (until the creator removes the
  voice); the design's search-at-runtime approach is the correct mitigation
- No documented per-endpoint rate limits; SDK handles 429 with
  exponential back-off; negligible risk for ~20-character books

### R2 — Actor voices not available via API (RED for named actors)

- No official ElevenLabs-licensed voices for Daniel Radcliffe, Emma Watson,
  Ian McKellen, or any current franchise film actors exist in the Voice
  Library API
- ElevenLabs' Iconic Marketplace (launched March 2026) has licensed celebrity
  voices (Judy Garland, Sir Michael Caine, Sir Laurence Olivier, etc.) but:
  (a) it has none of the target franchise actors, and
  (b) it has **no programmatic API** — manual licensing only via "Contact Sales"
- Community clones with actor names (e.g., "Daniel Radcliffe") exist in the
  `cloned` category but quality is inconsistent and cannot be relied upon

### R3 — ToS prohibits commercial use of celebrity clones (AMBER)

- Programmatic search and use of the Voice Library API is **permitted**
- Using community voices that replicate a real person's voice without their
  consent for commercial production is **prohibited** (Prohibited Use Policy §5(a))
- Community actor-clone voices for commercial audiobooks are therefore
  out of scope
- The Voice Library Addendum (a separate ToS document) returned 404 — must
  be retrieved from the account dashboard before shipping and reviewed for
  any additional constraints

### Scope consequence

Actor-name search is replaced by **vocal-characteristic search**. The book
identifier still resolves which actor played each character; that mapping is
then used to look up the actor's known vocal profile (gender, age, accent)
and find a high-quality non-clone voice that matches those characteristics.
The experience is "voices chosen for each character's demographic, informed
by the film cast's profiles" rather than "literally the actors' voices."

---

## Acceptance criteria

### 1. Book recognition

A new `src/ai/book_identifier.py` module exposes:

```python
@dataclass
class ActorProfile:
    actor_name: str         # e.g. "Daniel Radcliffe"
    gender: str             # "male" | "female"
    age: str                # "young" | "middle_aged" | "old"
    accent: str             # e.g. "british" | "american" | "irish"

@dataclass
class AdaptationCast:
    book_title: str                          # canonical title
    adaptation_title: str                    # e.g. "Harry Potter and the Sorcerer's Stone (2001 film)"
    character_profiles: dict[str, ActorProfile]  # character_name → actor profile
    confidence: float                        # 0.0–1.0
```

The module calls Claude with the book title and first-chapter character list.
The prompt asks: "Is this a well-known title with a movie or TV adaptation?
If so, for each character, name the actor who played them and describe their
voice (gender, age bracket, accent)." The prompt requires JSON output and
instructs the model to set `confidence < 0.8` when uncertain.

### 2. Voice Library search by characteristic

`src/tts/voice_library_search.py` exposes:

```python
def search_voice_by_profile(
    profile: ActorProfile,
    client: ElevenLabs,
    min_weekly_uses: int = 5_000,
) -> str | None:
    """
    Search the public Voice Library for a professional or high-quality voice
    matching the actor's vocal profile. Returns a voice_id or None.
    """
```

Search strategy (in order, stop at first hit returning ≥ 1 result):

1. `category="professional"` + `gender` + `age` + `accent`
2. `category="high_quality"` + `gender` + `age` + `accent`
3. `category=None` (all) + `gender` + `age` + `accent`, filtered client-side
   to `usage_character_count_7d >= min_weekly_uses`

From each result set, prefer the voice with the highest
`usage_character_count_7d` (a proxy for community quality signal). Return
its `voice_id`. If the result set is empty after all three queries,
return `None`.

Actor-name search (`search=actor_name`) is **not used** in Phase 1 (ToS
constraint on community celebrity clones). The `cloned` category is excluded
from all queries.

Results are cached in-process (dict keyed by `(gender, age, accent)`) to
avoid redundant API calls when multiple characters share the same profile.

Handle `404` on subsequent TTS synthesis (voice removed between search and
synthesis) by catching the exception and returning to demographic fallback.

### 3. Domain model

Add to `src/domain/models.py`:

```python
class CastingSource(str, Enum):
    DEMOGRAPHIC  = "demographic"   # existing behaviour
    CINEMATIC    = "cinematic"     # characteristic-matched to film cast profile
```

`Character` gains `casting_source: CastingSource = CastingSource.DEMOGRAPHIC`.

### 4. Voice assignment integration

In the voice assignment step:

1. Run `book_identifier` on book title + character list.
2. If `confidence >= 0.8`, for each character in `character_profiles`, call
   `search_voice_by_profile(profile)`.
3. If a `voice_id` is returned, assign it and set `casting_source = CINEMATIC`.
4. Characters with no match fall through to existing demographic assignment.
5. If `confidence < 0.8` or recognition fails, skip cinematic casting entirely.

### 5. Output and observability

- `book.json` includes `casting_source` on each character.
- Log at `INFO` level: book recognised, which characters got cinematic voices,
  which fell back.
- `make verify` output includes `casting_source` values in `output.json`.

### 6. Opt-out flag

`--no-cinematic-cast` CLI flag forces demographic assignment. Useful for
non-famous books and for testing.

### 7. Voice Library Addendum review (pre-ship gate)

Before the PR is merged, retrieve the Voice Library Addendum from the
ElevenLabs account dashboard and confirm it contains no additional
restrictions on programmatic use in automated pipelines. Document the
outcome in a comment on this spec.

### 8. Tests

- Unit test: `book_identifier` returns `confidence < 0.8` for a fictional
  unknown title (mock the AI call — 1 mock)
- Unit test: `search_voice_by_profile` returns `None` when all three queries
  return empty results (mock the ElevenLabs client — 1 mock)
- Unit test: `Character` round-trips `casting_source` through
  `to_dict` / `from_dict`
- Integration marker: `@pytest.mark.integration` test that calls the real
  `GET /v1/shared-voices` for `gender="male", age="young", accent="british"`
  and asserts at least one voice is returned (skipped unless
  `ELEVENLABS_API_KEY` is set)

---

## Out of scope

- Actor-name search or use of `cloned` category voices (ToS §5(a))
- Voice cloning or custom voice upload
- Narrator voice — cinematic casting applies to named characters only
- TV series adaptations beyond the first season's core cast
- Non-English adaptations
- Books without a recognised movie/TV adaptation

---

## Phase 2 (future, dependent on Iconic Marketplace API)

ElevenLabs' Iconic Marketplace is the legitimate path to licensed actor
voices. It currently has no programmatic API. When one becomes available:

- Extend `search_voice_by_profile` to query Iconic Marketplace first, using
  `actor_name`, before falling back to characteristic search
- Submit a request to ElevenLabs Sales to add Harry Potter, LOTR, and
  Pride & Prejudice cast members to the Marketplace
- At that point the feature delivers voices that genuinely evoke the film
  cast, not just demographically similar alternatives

Track: ElevenLabs Iconic Marketplace API announcements. No code changes are
needed to the calling architecture — only `voice_library_search.py` changes.

---

## Key design decisions

### Characteristic search instead of actor-name search
Searching by `actor_name` in Phase 1 would surface `cloned` category voices
whose commercial use is ToS-non-compliant. Searching by `gender + age +
accent + category=professional/high_quality` is compliant and still produces
better voice selection than raw demographic matching, because the actor's
known vocal profile guides the search (e.g., "young British male" for
Harry Potter vs a generic age/sex match against the ElevenLabs stock list).

### Weekly-use count as quality proxy
The `usage_character_count_7d` field is the best available quality signal
in the public Voice Library API. High-use voices have been evaluated by many
users. The 5,000 character/week floor filters out obscure or untested voices.
This threshold can be tuned after observing real results.

### `cloned` category excluded entirely
Even community voices that happen not to clone real people live in the
`cloned` category. Excluding it wholesale avoids needing to inspect each
voice's description for celebrity references. The `professional` and
`high_quality` categories are safer and higher quality anyway.

### Confidence threshold at 0.8
A misidentified title would produce absurd casting. Failing safe to
demographic assignment is always correct when confidence is low.

### Search-at-runtime, never hardcode voice IDs
Community voice IDs are stable while the voice exists but can be removed.
Search-at-runtime ensures that if a voice disappears, the next run finds the
next-best match automatically.

---

## Risks and mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Voice Library Addendum (currently 404) contains additional restrictions | Unknown | Pre-ship gate (AC7) — do not merge without reviewing it |
| Characteristic search returns no results for an unusual profile | Low–Medium | Three-tiered fallback; last tier relaxes category filter |
| LLM hallucinates cast for non-famous book | Medium | Confidence threshold; opt-out flag; log all cinematic assignments |
| ElevenLabs adds Iconic Marketplace API, making Phase 2 relevant sooner | Medium | Architecture is already Phase-2-ready; only `voice_library_search.py` needs updating |
| ToS changes restrict automated Voice Library use | Low | Monitor ToS; pre-ship gate AC7 catches current state |

---

## Files expected to change

| File | Change |
|---|---|
| `src/domain/models.py` | Add `CastingSource` enum; add `casting_source` field to `Character` |
| `src/ai/book_identifier.py` | New module — LLM-based book/cast recognition → `ActorProfile` map |
| `src/tts/voice_library_search.py` | New module — characteristic-based Voice Library search |
| `src/workflows/ai_project_gutenberg_workflow.py` | Wire cinematic casting into voice assignment |
| `src/main.py` | Add `--no-cinematic-cast` CLI flag |
| `src/ai/book_identifier_test.py` | New unit tests |
| `src/tts/voice_library_search_test.py` | New unit tests |
| `tests/test_cinematic_cast_integration.py` | Integration test (skipped without API key) |
