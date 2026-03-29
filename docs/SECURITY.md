# Security Guidelines

## Core Rule: No Secrets in Source

**All API keys, credentials, tokens, and secrets must live in environment variables.**

Never commit secrets to version control. Never hardcode secrets in source files.

## Configuration Pattern

Use the `config` module to load secrets from environment variables:

```python
from src.config.config import Config

config = Config.from_env()
# config.aws.access_key_id loaded from AWS_ACCESS_KEY_ID env var
# config.elevenlabs_api_key loaded from ELEVENLABS_API_KEY env var
```

## Required Environment Variables

### AWS Credentials (for AI section parsing)

```bash
export AWS_REGION=us-east-1
export AWS_BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-6

# Optional: AWS credentials (defaults to AWS credential chain)
export AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
export AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
export AWS_SESSION_TOKEN=...  # if using temporary credentials
```

### ElevenLabs API Key (future TTS integration)

```bash
export ELEVENLABS_API_KEY=sk_...
```

## Validation at Startup

The `Config` class validates required secrets at startup. If a required secret is missing, the program fails immediately with a clear error message:

```python
config = Config.from_cli()
config.validate()  # raises SystemExit if required secrets are missing
```

This fail-fast approach prevents the program from running with missing credentials and failing deep in the execution path.

## Credential Chain Fallback

AWS credentials support the standard AWS credential chain:

1. Environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`)
2. AWS credentials file (`~/.aws/credentials`)
3. IAM role (if running on EC2, ECS, Lambda, etc.)

If environment variables are not set, boto3 will try the other methods automatically. This allows the code to work in different environments (local dev, CI, production) without modification.

## Local Development

For local development, use a `.env` file (gitignored) and load it with a tool like `direnv` or `python-dotenv`:

```bash
# .env (this file is in .gitignore)
AWS_REGION=us-east-1
AWS_BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-6
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
```

**Never commit `.env` to version control.**
