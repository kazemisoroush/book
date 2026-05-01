# Config Package

1. Config Layer: `src/config/config.py` contains all application configuration that flows to the code. Support either CLI or Environment Variables not both at the same time.

2. Feature Flags: `src/feature_flags.py` hardcoded deterministic toggles. Not configurable from anywhere else, edit the file to change defaults. Feature flags must only gate deterministic code; anything that mutates prompt text belongs in the prompt template, not here.
