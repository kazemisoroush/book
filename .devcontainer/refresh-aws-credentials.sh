#!/bin/bash
# AWS Credential Refresh Script
# Automatically refreshes AWS credentials if they're expired or about to expire

set -e

PROFILE="${AWS_PROFILE:-bedrock}"
REGION="${AWS_REGION:-us-east-1}"

# Color output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Checking AWS credentials for profile: $PROFILE${NC}"

# Check if credentials are valid
if aws sts get-caller-identity --profile "$PROFILE" &>/dev/null; then
    ACCOUNT=$(aws sts get-caller-identity --profile "$PROFILE" --query Account --output text 2>/dev/null)
    USER_ARN=$(aws sts get-caller-identity --profile "$PROFILE" --query Arn --output text 2>/dev/null)

    echo -e "${GREEN}✓ AWS credentials are valid${NC}"
    echo -e "  Account: ${ACCOUNT}"
    echo -e "  Identity: ${USER_ARN}"
    exit 0
fi

echo -e "${RED}✗ AWS credentials are expired or invalid${NC}"
echo -e "${YELLOW}Attempting to refresh credentials...${NC}"

# Check if using SSO or AWS login
if grep -q "sso_" ~/.aws/config 2>/dev/null; then
    echo -e "${YELLOW}Detected SSO configuration, initiating SSO login...${NC}"
    aws sso login --profile "$PROFILE"

    if aws sts get-caller-identity --profile "$PROFILE" &>/dev/null; then
        echo -e "${GREEN}✓ SSO login successful${NC}"
        exit 0
    fi
elif grep -q "login_session" ~/.aws/config 2>/dev/null; then
    echo -e "${YELLOW}Detected AWS login session authentication${NC}"
    echo -e "${YELLOW}⚠️  This requires browser authentication - run: aws login --profile $PROFILE${NC}"
    echo -e "${YELLOW}Note: Automatic refresh is not possible for browser-based login${NC}"
    exit 1
fi

# Check if using regular IAM credentials (check if credentials file exists in host)
if [ -n "$AWS_SHARED_CREDENTIALS_FILE" ] && [ -f "$AWS_SHARED_CREDENTIALS_FILE" ]; then
    echo -e "${YELLOW}Detected IAM credential file: $AWS_SHARED_CREDENTIALS_FILE${NC}"
    echo -e "${YELLOW}ℹ Please ensure your host credentials are up to date${NC}"
fi

# Try to use AWS CLI to get session token (for MFA-enabled accounts)
if aws sts get-session-token --profile "$PROFILE" &>/dev/null; then
    echo -e "${GREEN}✓ Session token obtained${NC}"
    exit 0
fi

# If we get here, credentials couldn't be refreshed
echo -e "${RED}✗ Failed to refresh AWS credentials${NC}"
echo -e "${YELLOW}ℹ Possible solutions:${NC}"
echo -e "  1. Check that your host AWS credentials are valid"
echo -e "  2. Run 'aws configure --profile $PROFILE' to update credentials"
echo -e "  3. Claude Code will fall back to ANTHROPIC_API_KEY if configured"
exit 1
