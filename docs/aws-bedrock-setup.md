# AWS Bedrock Setup for Character Registry

This project uses AWS Bedrock with Claude models for AI-powered character identification and dialogue classification.

## Why AWS Bedrock?

- **No local memory required**: Runs in the cloud, perfect for constrained environments
- **High quality**: Uses Claude Sonnet 4.5 (same model powering this assistant)
- **Pay-per-use**: No upfront costs, only pay for what you use
- **Production ready**: Scalable, reliable AWS infrastructure

## Prerequisites

1. **AWS Account**: You need an AWS account
2. **Bedrock Access**: Request access to Anthropic Claude models in AWS Bedrock console
3. **AWS Credentials**: Either IAM role or access keys

## Configuration

All configuration is done via environment variables. See `.env.example` for full details.

### Method 1: Environment Variables (Recommended)

```bash
# Set AWS region
export AWS_REGION=us-east-1

# Set the Claude model to use (optional - has good default)
export AWS_BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-20250514-v1:0

# If not using default AWS credential chain, set credentials:
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
```

### Method 2: AWS Credential Chain (Default)

If you don't set credentials in environment variables, the SDK will use the standard AWS credential chain:

1. Environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`)
2. AWS credentials file (`~/.aws/credentials`)
3. IAM role (if running on EC2/ECS/Lambda)
4. ECS container credentials
5. EC2 instance metadata

**To set up AWS credentials file:**

```bash
aws configure
```

This creates `~/.aws/credentials` with your access keys.

## Available Models

Choose the model that fits your needs and budget:

### Claude Sonnet 4.5 (Recommended)
- **Model ID**: `us.anthropic.claude-sonnet-4-20250514-v1:0`
- **Best for**: Production use, balanced performance and cost
- **Speed**: Fast
- **Cost**: Moderate

### Claude Opus 4
- **Model ID**: `us.anthropic.claude-opus-4-20250514-v1:0`
- **Best for**: Highest accuracy requirements
- **Speed**: Slower
- **Cost**: Higher

### Claude 3.5 Sonnet
- **Model ID**: `anthropic.claude-3-5-sonnet-20241022-v2:0`
- **Best for**: Alternative if Sonnet 4.5 not available in your region
- **Speed**: Fast
- **Cost**: Lower

## Region Availability

AWS Bedrock is available in select regions. As of 2025, these regions support Claude models:

- `us-east-1` (US East N. Virginia) ✅ Recommended
- `us-west-2` (US West Oregon)
- `eu-west-1` (Europe Ireland)
- `ap-southeast-1` (Asia Pacific Singapore)
- `ap-northeast-1` (Asia Pacific Tokyo)

**Check current availability**: [AWS Bedrock Regions](https://docs.aws.amazon.com/bedrock/latest/userguide/what-is-bedrock.html#bedrock-regions)

## Usage in Code

```python
from src.config import get_config
from src.ai.aws_bedrock_provider import AWSBedrockProvider

# Configuration is automatically loaded from environment
config = get_config()

# Initialize the provider
ai_provider = AWSBedrockProvider(config)

# Classify dialogue
result = ai_provider.classify_dialogue(
    paragraph='"Hello," said Elizabeth.',
    context={'known_characters': ['Elizabeth Bennet']}
)

print(f"Is dialogue: {result.is_dialogue}")
print(f"Speaker: {result.speaker}")

# Resolve speaker
speaker = ai_provider.resolve_speaker(
    descriptor='his wife',
    context={
        'paragraph': 'Mr. Bennet and his wife were talking.',
        'known_characters': ['Mrs. Bennet']
    }
)
print(f"Resolved speaker: {speaker}")

# Extract characters from book
characters = ai_provider.extract_characters(book_content)
print(f"Found {len(characters)} characters")
```

## Cost Estimation

Based on Claude Sonnet 4.5 pricing (as of 2025):
- Input: ~$3 per million tokens
- Output: ~$15 per million tokens

**Typical usage for a novel:**
- Character extraction (one-time): 10,000 tokens ≈ $0.03
- Speaker resolution: ~100 calls × 500 tokens ≈ $0.15
- Dialogue classification: ~500 calls × 300 tokens ≈ $0.45

**Total for processing a novel: ~$0.63**

## Troubleshooting

### AccessDeniedException
```
Error: An error occurred (AccessDeniedException) when calling the InvokeModel operation
```

**Solution**: Request access to Claude models in AWS Bedrock console:
1. Go to AWS Bedrock console
2. Navigate to "Model access"
3. Request access to Anthropic Claude models
4. Wait for approval (usually instant)

### ModelNotFoundException
```
Error: Could not resolve the foundation model from the model identifier
```

**Solution**: Check that:
1. Model ID is correct
2. Model is available in your region
3. You have access to the model in Bedrock console

### CredentialsError
```
Error: Unable to locate credentials
```

**Solution**:
1. Set AWS credentials in environment variables, or
2. Run `aws configure` to set up credentials file, or
3. Use IAM role if running on AWS infrastructure

### ThrottlingException
```
Error: Rate exceeded
```

**Solution**: AWS Bedrock has rate limits. For high-volume processing:
1. Implement exponential backoff (already built into boto3)
2. Request higher limits via AWS Support
3. Use batching where possible

## Testing

All AI provider functionality is fully tested with mocks (no AWS API calls during tests):

```bash
# Run all AI tests
python3 -m pytest src/ai/ -v

# Run specific tests
python3 -m pytest src/ai/aws_bedrock_provider_test.py -v
```

## Security Best Practices

1. **Never commit credentials**: Use environment variables or AWS credential chain
2. **Use IAM roles**: When running on AWS infrastructure, use IAM roles instead of access keys
3. **Rotate keys**: Regularly rotate access keys if using them
4. **Least privilege**: Grant only necessary permissions (bedrock:InvokeModel)
5. **Use .gitignore**: Ensure `.env` files are ignored by git

## Example IAM Policy

Minimal policy for Bedrock access:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "BedrockInvokeModel",
            "Effect": "Allow",
            "Action": [
                "bedrock:InvokeModel"
            ],
            "Resource": [
                "arn:aws:bedrock:us-east-1::foundation-model/us.anthropic.claude-sonnet-4*"
            ]
        }
    ]
}
```
