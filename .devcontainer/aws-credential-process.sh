#!/bin/bash
# AWS Credential Process - Provides fresh credentials on-demand
# Used by AWS SDK via credential_process configuration
# Returns credentials in JSON format as per AWS spec
# Works with JWT-based login credentials

PROFILE="${1:-bedrock}"

# For JWT-based login, we need to use the AWS CLI's internal credential resolution
# Export credentials using aws configure export-credentials (requires AWS CLI v2)
if command -v aws &> /dev/null; then
    # Try to get credentials using AWS CLI's built-in export
    CREDS_JSON=$(aws configure export-credentials --profile "$PROFILE" --format process 2>/dev/null)

    if [ $? -eq 0 ] && [ -n "$CREDS_JSON" ]; then
        echo "$CREDS_JSON"
        exit 0
    fi
fi

# Fallback: try to read from credentials file if export-credentials isn't available
ACCESS_KEY=$(aws configure get aws_access_key_id --profile "$PROFILE" 2>/dev/null)
SECRET_KEY=$(aws configure get aws_secret_access_key --profile "$PROFILE" 2>/dev/null)
SESSION_TOKEN=$(aws configure get aws_session_token --profile "$PROFILE" 2>/dev/null)
EXPIRATION=$(aws configure get aws_session_expiration --profile "$PROFILE" 2>/dev/null)

# Check if we have credentials
if [ -z "$ACCESS_KEY" ] || [ -z "$SECRET_KEY" ]; then
    echo '{"Error": "No AWS credentials found. Run: aws login --profile '$PROFILE'"}' >&2
    exit 1
fi

# Output JSON format required by credential_process
if [ -n "$SESSION_TOKEN" ]; then
    cat <<EOF
{
  "Version": 1,
  "AccessKeyId": "$ACCESS_KEY",
  "SecretAccessKey": "$SECRET_KEY",
  "SessionToken": "$SESSION_TOKEN",
  "Expiration": "$EXPIRATION"
}
EOF
else
    cat <<EOF
{
  "Version": 1,
  "AccessKeyId": "$ACCESS_KEY",
  "SecretAccessKey": "$SECRET_KEY"
}
EOF
fi
