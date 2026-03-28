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
export AWS_BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-20250514-v1:0

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

## What NOT to Do

**Bad** - Hardcoded secret:

```python
api_key = "sk_1234567890abcdef"
```

**Bad** - Secret in config file committed to git:

```yaml
# config.yaml (DON'T DO THIS)
api_key: sk_1234567890abcdef
```

**Bad** - Secret in command-line argument (visible in process list):

```bash
python main.py --api-key sk_1234567890abcdef
```

**Good** - Environment variable:

```bash
export ELEVENLABS_API_KEY=sk_1234567890abcdef
python main.py
```

## Local Development

For local development, use a `.env` file (gitignored) and load it with a tool like `direnv` or `python-dotenv`:

```bash
# .env (this file is in .gitignore)
AWS_REGION=us-east-1
AWS_BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-20250514-v1:0
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
```

**Never commit `.env` to version control.**

## CI/CD

In GitHub Actions or other CI systems, use secret management features:

```yaml
# .github/workflows/test.yml
env:
  AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
  AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
```

## Production Deployment

In production (EC2, ECS, Lambda), use IAM roles instead of access keys. The boto3 client will automatically use the instance role credentials.

## Rotating Credentials

If a credential is accidentally committed:

1. Rotate the credential immediately (invalidate the old one)
2. Use `git filter-branch` or BFG Repo-Cleaner to remove it from history
3. Force-push the cleaned history (or create a new repo if necessary)

Prevention is better than remediation. Use pre-commit hooks to scan for common secret patterns.

## Additional Security Considerations

- **Least privilege**: Use IAM policies that grant only the permissions needed (e.g., `bedrock:InvokeModel` only)
- **Temporary credentials**: Prefer AWS STS temporary credentials over long-lived access keys
- **Audit logs**: Enable CloudTrail to log all Bedrock API calls for security auditing
- **Rate limiting**: Implement rate limiting on expensive AI calls to prevent abuse
- **Input validation**: Validate all external input (URLs, file paths) before processing

## Contact

If you discover a security issue, contact the repository owner immediately. Do not open a public GitHub issue for security vulnerabilities.
