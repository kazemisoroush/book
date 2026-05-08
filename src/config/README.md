# Config

Application configuration: typed config dataclasses (AWS, Anthropic, CLI, root) loaded from environment variables or CLI flags, plus deterministic feature flags.

## AWSConfig

## AnthropicConfig

## Config

`src/config/config.py` contains all application configuration that flows to the code. Support either CLI or Environment Variables not both at the same time.

## CLIConfig

## FeatureFlags

`src/feature_flags.py` hardcoded deterministic toggles. Not configurable from anywhere else, edit the file to change defaults. Feature flags must only gate deterministic code; anything that mutates prompt text belongs in the prompt template, not here.
