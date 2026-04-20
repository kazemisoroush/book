# TD-022 — Preserve Expensive Artifacts

## Problem

The pipeline destroys or loses expensive intermediate artifacts. TTS segments
are synthesised into a `tempfile.TemporaryDirectory` and deleted after
stitching — re-running a chapter re-pays $0.01-$0.10 per segment ($30-$300 per
book). `book.json` (the ~$150 AI parse result) is gitignored via a blanket
`books/` exclusion, so a workspace wipe loses it. Ambient/SFX/music caches use
a flat `{cache_dir}/{filename}.mp3` structure — switching providers silently
serves stale audio from the wrong provider.

## Proposed Solution

**TTS segments**: Replace the temp directory with a permanent
`segments/{provider_name}/` folder under each chapter's audio directory. Before
calling the TTS API, check if `seg_NNNN.mp3` already exists (size > 0) — skip
if cached.

**Ambient/SFX/music caches**: Change cache paths from `{cache_dir}/{filename}`
to `{cache_dir}/{provider_name}/{filename}`.

**Provider `name` property**: Add an abstract `name` property to `TTSProvider`,
`AmbientProvider`, `SoundEffectProvider`, and `MusicProvider` ABCs. Each
concrete provider returns its identifier (e.g. `"fish_audio"`, `"elevenlabs"`,
`"audiogen"`, `"suno"`). This namespaces all cached artifacts per provider.

**book.json**: Replace the blanket `books/` gitignore with specific patterns
for audio/download artifacts (`*.mp3`, `*.wav`, `*.html`, `*.txt`,
`concat_list.txt`). This makes `book.json` trackable by git while keeping
binaries out of the repo.
