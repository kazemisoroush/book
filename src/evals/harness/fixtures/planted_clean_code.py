"""Planted clean-code violations for the Clean Code Auditor eval.

NOT production code — intentionally placed for the eval scorer to plant
into temporary locations. The Clean Code Auditor should detect each
violation when scanning.

Each violation is tagged with the rule it violates in its comment so
the scorer can report per-rule recall/precision.
"""

# ── Rule 1: Direct env var access outside config ──────────────────────────

# VIOLATION: rule-1-env-var
RULE_1_CODE = '''\
"""Planted module with env var access — rule 1 violation."""
import os

def get_api_key() -> str:
    return os.environ.get("ELEVENLABS_API_KEY", "")
'''

# ── Rule 2: Bare print in production code ─────────────────────────────────

# VIOLATION: rule-2-bare-print
RULE_2_CODE = '''\
"""Planted module with bare print — rule 2 violation."""

def process_beat(text: str) -> str:
    print(f"Processing: {text}")
    return text.upper()
'''

# ── Rule 3: Unseeded random in domain ─────────────────────────────────────

# VIOLATION: rule-3-unseeded-random
RULE_3_CODE = '''\
"""Planted module with unseeded random — rule 3 violation."""
import random

def pick_voice() -> str:
    voices = ["alice", "bob", "charlie"]
    return random.choice(voices)
'''

# ── Rule 4: Provider naming convention ────────────────────────────────────

# VIOLATION: rule-4-naming-convention
RULE_4_CODE = '''\
"""Planted module with wrong provider naming — rule 4 violation."""
from src.audio.tts.tts_provider import TTSProvider
from pathlib import Path
from typing import Optional


class SunoProvider(TTSProvider):
    """Should be SunoTTSProvider, not SunoProvider."""

    def synthesize(
        self,
        text: str,
        voice_id: str,
        output_path: Path,
        emotion: Optional[str] = None,
        previous_text: Optional[str] = None,
        next_text: Optional[str] = None,
        voice_stability: Optional[float] = None,
        voice_style: Optional[float] = None,
        voice_speed: Optional[float] = None,
        previous_request_ids: Optional[list[str]] = None,
    ) -> Optional[str]:
        return None

    def get_available_voices(self) -> dict[str, str]:
        return {}
'''

# ── Clean code (no violations) ────────────────────────────────────────────

CLEAN_CODE = '''\
"""Planted clean module — no violations."""
import structlog

from src.config import get_config

logger = structlog.get_logger(__name__)


def get_api_key() -> str:
    """Get API key through config layer."""
    config = get_config()
    return config.elevenlabs_api_key or ""
'''
