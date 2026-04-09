"""Planted spec request for spec-writer eval.

Provides a rough feature request that the Spec Writer agent
must transform into a well-structured spec file.
"""

# A deliberately rough, informal feature request — the kind of input
# a human would give the spec writer. The agent must produce a proper
# spec from this.
SPEC_REQUEST = """\
I want to add chapter-level bookmarks to the audiobook output. Right now
the assembled MP3 is one long file with no way to skip to a specific chapter.
I want the assembler to embed ID3 chapter markers so podcast players and
audiobook apps can show a chapter list. Each marker should have the chapter
title and start time. Only chapters that were actually synthesized should
get markers (skipped chapters should not appear). The domain model probably
needs a ChapterMarker dataclass. The assembler already uses ffmpeg so we
should be able to use ffmpeg chapter metadata for this.
"""

# What a correct spec MUST contain (used by scorer)
EXPECTED_PREFIX = "US"
EXPECTED_SLUG_WORDS = ["chapter", "bookmark"]  # at least one must appear in filename

# Acceptance criteria that MUST appear (by keyword matching)
REQUIRED_CRITERIA_KEYWORDS = [
    "ChapterMarker",          # must mention the dataclass
    "chapter title",          # must mention what the marker contains
    "start time",             # must mention timing
    "ffmpeg",                 # must mention the implementation tool
    "skipped",                # must handle skipped chapters
]

# Sections that MUST be present in the spec
REQUIRED_SECTIONS = [
    "Goal",
    "Acceptance criteria",
    "Out of scope",
]

# Things that should NOT be in the spec (precision checks)
FORBIDDEN_CONTENT = [
    "import ",          # no code imports — it's a spec, not implementation
    "def ",             # no function definitions
    "class ",           # no class definitions (signatures in AC are OK as markdown code blocks)
]
