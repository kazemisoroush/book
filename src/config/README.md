# Config

Application configuration: typed config dataclasses (AWS, Anthropic, CLI, root) loaded from environment variables or CLI flags, plus deterministic feature flags.

## AWSConfig

`src/config/config.py` contains AWS auth configuration used for Bedrock foundation model.

## AnthropicConfig

`src/config/config.py` contains Anthropic configuration for accessing foundation model.

## Config

`src/config/config.py` contains all application configuration that flows to the code. Support either CLI or Environment Variables not both at the same time.

### `PROVIDER` (unified provider knob)

A single `PROVIDER` env var selects the concrete backend across every axis. Each `_build_*` in `workflow_factory.py` reads `config.provider` and falls back to its axis default when the value is unrecognized.

| Axis    | Values                  | Default     |
| ------- | ----------------------- | ----------- |
| ai      | `anthropic`, `bedrock`  | `bedrock`   |
| tts     | `elevenlabs`, `fish`    | `fish`      |
| ambient | `audiogen`, `elevenlabs`| `elevenlabs`|
| sfx     | `audiogen`, `elevenlabs`| `elevenlabs`|

Example: `PROVIDER=elevenlabs python main.py --workflow tts ...` runs TTS with ElevenLabs; `PROVIDER=audiogen python main.py --workflow ambient ...` runs ambient with AudioGen.

## CLIConfig

`src/config/config.py` application configuration coming out of CLI arguments.

## FeatureFlags

`src/feature_flags.py` hardcoded deterministic toggles. Not configurable from anywhere else, edit the file to change defaults. Feature flags must only gate deterministic code; anything that mutates prompt text belongs in the prompt template, not here.
