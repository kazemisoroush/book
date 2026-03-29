# Research Report: US-013 Cinematic Voice Casting

**Date:** 2026-03-29
**Researcher:** Claude Sonnet 4.6
**Scope:** Three gating questions (R1, R2, R3) that must be resolved before US-013 can be implemented.

---

## Executive Summary

- **R1 — API confirmed viable.** The ElevenLabs shared-voice search endpoint `GET /v1/shared-voices` exists, is fully parameterised, and returns stable `voice_id` values. The Python SDK exposes it as `client.voices.get_shared(search=...)`. Response objects include `voice_id`, `name`, `category`, and usage statistics. No documented per-endpoint rate limit was found; the SDK handles 429s with exponential back-off using `X-RateLimit-Reset` and `Retry-After` headers.

- **R2 — Celebrity voices are sparse and legally ambiguous in the public Voice Library.** No official ElevenLabs-licensed voices for Daniel Radcliffe, Emma Watson, Ian McKellen, Viggo Mortensen, or the other target actors appear to be available via the Voice Library API. ElevenLabs' formally licensed celebrity voices (the "Iconic Marketplace" programme) cover historical figures and a handful of living icons — not current film-franchise actors. Community-contributed clones with names like "Daniel Radcliffe" may exist in the library but cannot be relied upon for quality or continuity.

- **R3 — ToS compliance is amber, not green.** Programmatic API use of the shared Voice Library is explicitly permitted. However, using community voices that replicate a real person's voice without that person's consent violates the ElevenLabs Prohibited Use Policy (Section 5). Community actor-clone voices carry this risk. The "Iconic Marketplace" licensed voices are *not* available through the Voice Library API — they are walled off to the ElevenReader app and a separate marketplace requiring manual licensing negotiation.

- **The feature is feasible only if scoped to non-celebrity voices or the `famous`/`professional` category filter.** Programmatic search for voices *labelled* after living actors is on shaky ToS ground. A safer implementation searches by vocal characteristics (gender, age, accent) rather than by actor name, or defers all celebrity matching to the Iconic Marketplace (which has no API today).

- **Recommended scope reduction:** Implement the architecture as designed but substitute actor-name search with characteristic-based search in phase 1. Track the Iconic Marketplace API roadmap for a future phase 2 that delivers the full cinematic experience.

---

## R1 — ElevenLabs Voice Library Search API

### Confirmed Endpoints

Two distinct endpoints are relevant. They serve different purposes and should not be confused.

#### Endpoint A: `GET /v1/shared-voices` — Public Voice Library search

This is the primary endpoint for discovering voices contributed to the public Voice Library.

| Property | Value |
|---|---|
| HTTP method | `GET` |
| Path | `/v1/shared-voices` |
| Auth | `xi-api-key` header |
| SDK method | `client.voices.get_shared(...)` |
| Return type | `GetLibraryVoicesResponse` |

**Query parameters** (all optional):

| Parameter | Type | Notes |
|---|---|---|
| `search` | `str` | Free-text search across name and description |
| `page_size` | `int` | Max 100, default 30 |
| `page` | `int` | Offset-based pagination |
| `category` | `enum` | `"generated"`, `"cloned"`, `"premade"`, `"professional"`, `"famous"`, `"high_quality"` |
| `gender` | `str` | `"male"`, `"female"` |
| `age` | `str` | e.g. `"young"`, `"middle_aged"`, `"old"` |
| `accent` | `str` | e.g. `"british"`, `"american"` |
| `language` | `str` | ISO language code |
| `locale` | `str` | e.g. `"en-GB"` |
| `use_cases` | `str or list[str]` | Intended usage |
| `descriptives` | `str or list[str]` | Descriptive tags |
| `featured` | `bool` | Show only featured voices |
| `sort` | `str` | Sort field |
| `owner_id` | `str` | Filter by public owner |

**Response shape** (`LibraryVoiceResponse` per item in `voices` list):

```json
{
  "voices": [
    {
      "public_owner_id": "abc123",
      "voice_id": "TxGEqnHWrfWFTfGW9XjX",
      "name": "Daniel Radcliffe - Harry Potter",
      "description": "...",
      "accent": "british",
      "gender": "male",
      "age": "young",
      "category": "cloned",
      "use_case": "narration",
      "descriptive": "...",
      "preview_url": "https://...",
      "cloned_by_count": 1240,
      "usage_character_count_1y": 5000000,
      "usage_character_count_7d": 80000,
      "featured": false,
      "free_users_allowed": true,
      "live_moderation_enabled": false,
      "rate": null
    }
  ],
  "has_more": true,
  "last_sort_id": "..."
}
```

**Confidence: High.** Source: direct inspection of `elevenlabs-python` SDK source at `src/elevenlabs/voices/raw_client.py` and `src/elevenlabs/types/library_voice_response.py` via GitHub raw content (March 2026).

#### Endpoint B: `GET /v2/voices` — User voice search (not the public library)

| Property | Value |
|---|---|
| HTTP method | `GET` |
| Path | `/v2/voices` |
| SDK method | `client.voices.search(...)` |

This endpoint searches the *caller's own voice collection*, not the public library. It supports `voice_type=community` to include voices added from the library, but it is not a discovery endpoint. Use `/v1/shared-voices` for discovery.

### Example SDK Usage

```python
from elevenlabs.client import ElevenLabs

client = ElevenLabs(api_key="...")

# Search public library for voices matching "Daniel Radcliffe"
result = client.voices.get_shared(
    search="Daniel Radcliffe",
    page_size=10,
)

for voice in result.voices:
    print(voice.voice_id, voice.name, voice.category)
```

### voice_id Stability

`voice_id` values returned by `/v1/shared-voices` are the same IDs used in TTS synthesis calls. A voice ID passed to `client.text_to_speech.convert(voice_id, ...)` will work immediately without a separate "add to library" step — provided the voice remains in the public library.

**Stability caveat:** Community voices can be removed by their creator or by ElevenLabs moderation at any time. The spec's design decision to "search at runtime, never hardcode IDs" is the correct mitigation. A voice that disappears will yield no search result, and the fallback to demographic assignment triggers automatically.

**Confidence: High** (confirmed by SDK type definitions and general ElevenLabs platform documentation).

### Rate Limits

ElevenLabs does not publish per-endpoint rate limits in their public documentation (as of March 2026). The SDK HTTP client (`src/elevenlabs/core/http_client.py`) handles rate limiting via:
- `Retry-After` response header
- `X-RateLimit-Reset` response header (Unix timestamp)
- Exponential back-off with ±10% jitter when neither header is present
- Initial retry delay: 1.0 second; max retry delay: 60 seconds
- HTTP 429 treated as retryable

For a book with ~20 characters, the in-process cache described in the spec reduces voice library calls to at most 20 unique searches per book. At typical library search latency (100–300 ms per call) this is negligible. No rate limit risk identified for this use case.

**Confidence: Medium** (rate limit values are inferred from SDK source; no official published limits found).

---

## R2 — Celebrity / Actor Voice Availability

### Key Discovery: Two Separate Systems

ElevenLabs operates two distinct voice programs. They must not be confused:

**1. Voice Library (API-accessible)** — `GET /v1/shared-voices`
Thousands of voices contributed by the community. Anyone can upload a voice clone. The library includes voices labelled after real people, but ElevenLabs does not verify or license these. Quality varies widely.

**2. Iconic Marketplace (no API, manual licensing)**
Launched March 2026 at the ElevenLabs Summit. A curated, two-sided marketplace for licensed celebrity voices. Requires manual "Request Voice" negotiation. Current roster includes: Judy Garland, Sir Laurence Olivier, Sir Michael Caine, Dr. Maya Angelou, James Dean, Burt Reynolds, Alan Turing, J. Robert Oppenheimer, Art Garfunkel, John Wayne, and ~25 others. These voices are also available in the ElevenReader app for personal listening.

**Critical constraint:** Iconic Marketplace voices are explicitly described as "not part of our broader Voice Library for creating content to share" (ElevenLabs blog, March 2026). They are not accessible via `GET /v1/shared-voices` or any programmatic API.

### Per-Actor Assessment

The following table reflects available evidence. Direct API calls were not made (no API key in research environment). Assessments are based on: ElevenLabs platform documentation, Iconic Marketplace announcement (March 2026), general knowledge of the Voice Library's community-contributed content, and SDK category type definitions (`famous`, `cloned`, `professional`).

#### Harry Potter Cast

| Actor | Character | Official EL Voice? | Community Voice Available? | Search Term | Notes |
|---|---|---|---|---|---|
| Daniel Radcliffe | Harry Potter | No | Likely — numerous community clones exist | `"Daniel Radcliffe"` | Category: `cloned`. Quality inconsistent. Not verified. No official partnership announced. |
| Emma Watson | Hermione Granger | No | Likely | `"Emma Watson"` | Same caveats as Radcliffe. |
| Rupert Grint | Ron Weasley | No | Possible but sparse | `"Rupert Grint"` | Less prominent in voice clone communities. |
| Alan Rickman | Severus Snape | No (deceased) | Likely — distinctive voice widely cloned | `"Alan Rickman"` or `"Severus Snape"` | Rickman died 2016. No estate partnership announced. Community clones exist. |
| Richard Harris / Michael Gambon | Dumbledore | No (both deceased) | Possible | `"Richard Harris"`, `"Michael Gambon"` | Neither on Iconic Marketplace. Gambon died 2023. |

#### The Lord of the Rings Cast

| Actor | Character | Official EL Voice? | Community Voice Available? | Search Term | Notes |
|---|---|---|---|---|---|
| Ian McKellen | Gandalf | No | Likely | `"Ian McKellen"` or `"Gandalf"` | Very distinctive voice; widely reproduced. No official partnership. |
| Viggo Mortensen | Aragorn | No | Unlikely to be high quality | `"Viggo Mortensen"` | Less distinctive vocal profile for community cloners. |
| Elijah Wood | Frodo | No | Possible | `"Elijah Wood"` | Younger, lighter voice; fewer community clones expected. |
| Orlando Bloom | Legolas | No | Possible | `"Orlando Bloom"` | Similar to Wood. |
| Sean Astin | Samwise | No | Possible | `"Sean Astin"` | Moderate distinctiveness. |

#### Pride and Prejudice (2005 Film) Cast

| Actor | Character | Official EL Voice? | Community Voice Available? | Search Term | Notes |
|---|---|---|---|---|---|
| Keira Knightley | Elizabeth Bennet | No | Unlikely to be high quality | `"Keira Knightley"` | Limited vocal distinctiveness for cloning. |
| Matthew Macfadyen | Mr Darcy | No | Unlikely | `"Matthew Macfadyen"` | Very limited public profile in voice communities. |
| Brenda Blethyn | Mrs Bennet | No | Possible | `"Brenda Blethyn"` | More distinctive; some community clones may exist. |

### Quality and Reliability Assessment

The `category` field in `LibraryVoiceResponse` signals quality:
- `"professional"` — highest quality, ElevenLabs verified
- `"high_quality"` — high-quality community voices
- `"cloned"` — community voice clones, quality varies significantly
- `"famous"` — voices in the "famous" category (exact curation criteria undocumented, likely overlaps with Iconic Marketplace)
- `"premade"` — ElevenLabs stock voices
- `"generated"` — AI-designed voices

Celebrity actor clones will overwhelmingly be in the `cloned` category. The `famous` category may contain the Iconic Marketplace voices, but since those are explicitly gated, this cannot be relied upon.

**Bottom line:** Genuine, high-quality, licensed versions of the target film actors are not available in the Voice Library API. Community clones exist for the most famous actors (Radcliffe, Watson, McKellen, Rickman) but their quality, continuity, and ToS compliance are unreliable.

**Confidence: Medium.** A direct API call with a valid key would give definitive counts and quality scores. The finding that *no official licensed voices exist* for any of these actors is High confidence based on the Iconic Marketplace roster published in March 2026.

---

## R3 — Legal and Terms of Service Constraints

### Primary Sources Reviewed

- ElevenLabs Terms of Service (non-EEA), Last Updated 4 March 2026, fetched from `https://elevenlabs.io/terms-of-use`
- ElevenLabs Prohibited Use Policy, Last Updated 3 September 2025, fetched from `https://elevenlabs.io/use-policy`
- ElevenLabs Service-Specific Terms, Last Updated 27 March 2026, fetched from `https://elevenlabs.io/service-specific-terms`
- ElevenLabs Iconic Marketplace / Reader App announcements (blog, March 2026)

**Note:** The "Voice Library Addendum" referenced in the ToS as a separate document governing Voice Library use was not publicly accessible at any URL tested (returning 404). Its contents are unknown. This is itself a risk factor.

### Can Automated Pipelines Programmatically Search and Use Community Voices?

**Yes, with conditions.** The ToS grants a "limited, non-exclusive, non-transferable, non-sublicensable, revocable license to access and use our Services." Access via API is explicitly contemplated — the ToS references "application programming interfaces (APIs)" as part of the Services definition. No restriction on programmatic access to the Voice Library search endpoint was found.

The Prohibited Use Policy (Section 9.d) prohibits "data mining, robots, or similar data gathering or extraction methods designed to scrape or extract data from our Services, except in accordance with instructions contained in our robot.txt file." A search-and-synthesise workflow using the published API is distinct from scraping and is not prohibited by this clause.

**Confidence: High.**

### Commercial Use of Community Voices Resembling Public Figures

This is the critical constraint. The Prohibited Use Policy, Section 5, states:

> "Do not engage in unauthorized, deceptive or harmful impersonation. For example, this includes creating or using ElevenLabs audio output to intentionally replicate the voice of another person:
> (a) without consent or legal right, including to take unauthorized action on behalf of such individual;
> (b) in a way that harasses or causes harm to that person, including via unauthorized sexualization;
> (c) in a manner intended to deceive others about whether the voice was generated by artificial intelligence."

**Analysis:** Using a community-contributed voice labelled "Daniel Radcliffe" to produce commercial audiobook content:

- Falls under "(a)" if Daniel Radcliffe has not consented. There is no evidence he has.
- A user producing a paid audiobook product with that voice is using it for commercial purposes (ToS Section 1(c)(ii) permits commercial use for paid subscribers, but that does not override the Prohibited Use Policy).
- The intent is clearly to evoke the real actor's voice, making this replication "intentional."

**Verdict on celebrity community clones for commercial use: Non-compliant with ToS.** Even if the search succeeds and a voice is found, using it in a sold or commercially distributed audiobook is a ToS violation under Section 5(a) of the Prohibited Use Policy.

**Confidence: High.**

### Personal / Non-Commercial Use

Section 5(c) adds a separate restriction: the output must not be "intended to deceive others about whether the voice was generated by artificial intelligence." An AI audiobook does not inherently deceive if the AI origin is disclosed. For personal, non-commercial use with appropriate disclosure, the risk is lower but not eliminated (Section 5(a) still applies — the actor has not consented).

### Consent and Attribution Requirements

The ToS requires that any voice created or shared must have "all the rights necessary to grant us the license described above" (ToS Section 4(g)). ElevenLabs itself disclaims responsibility for community voices. The liability falls on the creator of the community clone (who uploaded an unauthorized celebrity voice sample) and potentially on the consumer who uses it knowing the consent is missing.

No attribution requirement for community voice *users* was found in the reviewed documents. However, the Voice Library Addendum (inaccessible) may contain additional requirements.

### ElevenLabs Officially Licensed Celebrity Voices

ElevenLabs' Iconic Marketplace (launched March 2026) is the legitimate channel for celebrity voices. The company explicitly describes its approach as "consent, and creative authenticity" and works through talent estates and agencies (CMG Worldwide). The Iconic Marketplace:
- Requires manual licensing negotiation ("Request Voice" button — no self-serve)
- Is not accessible via the Voice Library API
- Contains historical figures and a small set of living celebrities (none are current franchise film actors)
- Has no Daniel Radcliffe, Emma Watson, Ian McKellen, or any of the target actors

### ToS Verdict Summary

| Question | Finding |
|---|---|
| Programmatic search of Voice Library via API | Permitted |
| Using found `voice_id` in TTS synthesis | Permitted (subject to character consumption limits) |
| Commercial use of community voices that clone real actors without consent | Prohibited (Prohibited Use Policy §5(a)) |
| Non-commercial personal use of such voices | Technically prohibited (§5(a)), lower practical risk if AI origin disclosed |
| Iconic Marketplace voices via API | Not possible — no API access, manual licensing only |
| Attribution requirements for community voice users | None found in reviewed documents; Voice Library Addendum may add requirements |

**Overall ToS verdict: AMBER.** Programmatic access is fine; using community celebrity clones commercially is not.

---

## Feasibility Verdict

**AMBER**

### Rationale

The feature as described in US-013 is architecturally sound and technically implementable. The API exists, the SDK supports it, `voice_id` values are stable at runtime, and in-process caching is straightforward.

However, the scenario the spec was designed to deliver — "hear voices that evoke Daniel Radcliffe, Emma Watson, and Alan Rickman" — is blocked on two independent grounds:

1. **No licensed voices exist** for these actors in the Voice Library API. The Iconic Marketplace has the right ethical model but covers different celebrities and has no API.

2. **Community clones of living actors are ToS non-compliant** for commercial audiobook production.

The feature is not Red because the core infrastructure can be built and tested today using:
- Characteristic-based search (gender + age + accent) instead of actor-name search
- The `professional` and `high_quality` category filter to find non-celebrity high-quality voices
- The `famous` category to retrieve any Iconic Marketplace voices that do become API-accessible in future

It becomes fully Green when ElevenLabs either:
(a) Adds the franchise film actors (Radcliffe, Watson, McKellen, etc.) to the Iconic Marketplace with an API access path, or
(b) Expands the `famous` category in the Voice Library to include properly licensed versions

---

## Recommended Next Steps

### Immediate (before coding begins)

1. **Attempt a live API query** with a valid ElevenLabs API key to confirm what voices actually return for `search="Daniel Radcliffe"`, `search="Ian McKellen"`, etc. This takes 30 minutes and converts R2 confidence from Medium to High.

2. **Retrieve the Voice Library Addendum.** Log into the ElevenLabs account used for the project and navigate to the linked addendum. Extract any additional restrictions on community voice use in automated pipelines.

3. **Narrow the feature scope in the spec.** Revise US-013 to explicitly exclude community celebrity clones for commercial use. Replace actor-name search with characteristic-based search in the first shipped version.

### Implementation Phase 1 (characteristics-based, ToS-safe)

- Build `voice_library_search.py` as specified, but change the search strategy:
  - Instead of searching `actor_name`, search by `gender`, `age`, `accent` derived from the actor's known vocal profile.
  - Filter `category` to `professional` or `high_quality` to avoid low-quality clones entirely.
  - Return `None` if no voice meets a minimum `usage_character_count_7d` threshold (e.g. > 5,000), as a proxy for quality signal.
- Build `book_identifier.py` as specified — it can still identify the book and the actor map; the actor characteristics are then used for search rather than the actor's name.
- Ship this as the V1 of cinematic casting — it will not sound like Radcliffe specifically, but will select appropriate high-quality voices for each demographic profile.

### Implementation Phase 2 (actor-matched, dependent on Iconic Marketplace API)

- Monitor ElevenLabs Iconic Marketplace for an API endpoint (they have a "Contact Sales" path; no API currently announced).
- When an API becomes available, extend `search_actor_voice` to query the Iconic Marketplace first, fall back to characteristic search.
- Add franchise film actors (Harry Potter, LOTR, P&P) to the request list with ElevenLabs Sales.

### Architecture Notes for Implementers

- The `voice_id` returned by `GET /v1/shared-voices` is directly usable in `client.text_to_speech.convert(voice_id, ...)` — confirmed by SDK source.
- Use `client.voices.get_shared(search=..., category="professional", page_size=10)` as the first query. If no results, retry with `category="high_quality"`, then with `category=None` (all categories) but filter by `usage_character_count_7d > threshold` client-side.
- Handle `404` on synthesis (voice removed after search) by catching the API exception and returning to demographic fallback.
- The `voice_id` from the library does not need to be "added" to the user's account before use — shared library voices can be used directly. (Verify this against the Voice Library Addendum when it is retrieved.)

---

## Source Citations

| Source | URL | Accessed | Confidence |
|---|---|---|---|
| ElevenLabs Python SDK — voices/raw_client.py | github.com/elevenlabs/elevenlabs-python | 2026-03-29 | High |
| ElevenLabs Python SDK — types/library_voice_response.py | github.com/elevenlabs/elevenlabs-python | 2026-03-29 | High |
| ElevenLabs Python SDK — types/library_voice_response_model_category.py | github.com/elevenlabs/elevenlabs-python | 2026-03-29 | High |
| ElevenLabs Python SDK — core/http_client.py (rate limit handling) | github.com/elevenlabs/elevenlabs-python | 2026-03-29 | High |
| ElevenLabs Terms of Service (non-EEA), 4 March 2026 | elevenlabs.io/terms-of-use | 2026-03-29 | High |
| ElevenLabs Prohibited Use Policy, 3 September 2025 | elevenlabs.io/use-policy | 2026-03-29 | High |
| ElevenLabs Iconic Marketplace announcement (Michael Caine) | elevenlabs.io/blog/announcing-partnership-with-sir-michael-caine | 2026-03-29 | High |
| ElevenLabs Reader App + Iconic Voices announcement (Judy Garland et al.) | elevenlabs.io/blog/iconic-voices | 2026-03-29 | High |
| ElevenLabs Iconic Marketplace product page | elevenlabs.io/iconic-marketplace | 2026-03-29 | High |
| ElevenLabs Voice Library Addendum | elevenlabs.io/voice-library-addendum (404) | 2026-03-29 | NOT RETRIEVED |
| US-013 spec | docs/specs/us-013-cinematic-voice-casting.md | 2026-03-29 | High |
