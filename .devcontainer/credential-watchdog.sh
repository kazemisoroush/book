#!/bin/bash
# AWS Credential Watchdog - Auto-refresh credentials before expiry
# Runs continuously in the background to prevent "Could not load credentials" errors

set -e

PROFILE="${AWS_PROFILE:-bedrock}"
CHECK_INTERVAL_SECONDS=60  # Check every minute
EXPIRY_THRESHOLD_SECONDS=300  # Warn if less than 5 minutes remaining

# Color output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

get_jwt_expiration() {
    # Try to get expiration from AWS login cache JWT token
    local cache_file=$(find ~/.aws/login/cache -type f -name "*.json" 2>/dev/null | head -1)
    if [ -n "$cache_file" ] && [ -f "$cache_file" ]; then
        # Extract exp field from idToken JWT
        local exp=$(cat "$cache_file" | jq -r '.idToken' 2>/dev/null | cut -d. -f2 | base64 -d 2>/dev/null | jq -r '.exp' 2>/dev/null)
        if [ -n "$exp" ] && [ "$exp" != "null" ]; then
            echo "$exp"
            return 0
        fi
    fi
    return 1
}

check_and_refresh() {
    # Try to get caller identity - if this fails, credentials are invalid
    if ! IDENTITY=$(aws sts get-caller-identity --profile "$PROFILE" 2>&1); then
        log "${RED}✗ Credentials invalid or expired${NC}"
        log "${YELLOW}⚠️  Run 'aws login --profile $PROFILE' to refresh (requires browser)${NC}"
        return 1
    fi

    # Check JWT token expiration (for AWS login-based authentication)
    if JWT_EXP=$(get_jwt_expiration); then
        CURRENT_EPOCH=$(date +%s)
        SECONDS_REMAINING=$((JWT_EXP - CURRENT_EPOCH))

        if [ "$SECONDS_REMAINING" -lt 0 ]; then
            log "${RED}✗ JWT token has expired${NC}"
            log "${YELLOW}⚠️  Run 'aws login --profile $PROFILE' to refresh (requires browser)${NC}"
            return 1
        elif [ "$SECONDS_REMAINING" -lt "$EXPIRY_THRESHOLD_SECONDS" ]; then
            MINUTES_REMAINING=$((SECONDS_REMAINING / 60))
            log "${YELLOW}⚠️  JWT token expires in ${MINUTES_REMAINING}m - please run 'aws login --profile $PROFILE'${NC}"
            # Continue checking but warn user
        fi
    fi

    # If we have session credentials, check expiration time (for STS/assumed roles)
    if EXPIRY=$(aws configure get aws_session_expiration --profile "$PROFILE" 2>/dev/null); then
        # Calculate time until expiry
        EXPIRY_EPOCH=$(date -d "$EXPIRY" +%s 2>/dev/null || echo "0")
        CURRENT_EPOCH=$(date +%s)
        SECONDS_REMAINING=$((EXPIRY_EPOCH - CURRENT_EPOCH))

        if [ "$SECONDS_REMAINING" -lt "$EXPIRY_THRESHOLD_SECONDS" ]; then
            log "${YELLOW}⚠️  Session credentials expire in ${SECONDS_REMAINING}s - refreshing proactively${NC}"

            if /workspaces/apply/.devcontainer/refresh-aws-credentials.sh; then
                log "${GREEN}✓ Credentials refreshed successfully${NC}"
                return 0
            else
                log "${RED}✗ Failed to refresh credentials${NC}"
                return 1
            fi
        fi
    fi

    # Credentials are valid
    ACCOUNT=$(echo "$IDENTITY" | grep -o '"Account": "[^"]*"' | cut -d'"' -f4 2>/dev/null || echo "unknown")
    log "${GREEN}✓ Credentials valid (Account: ${ACCOUNT})${NC}"
    return 0
}

# Main loop
log "${BLUE}Starting AWS Credential Watchdog for profile: $PROFILE${NC}"
log "Check interval: ${CHECK_INTERVAL_SECONDS}s, Refresh threshold: ${EXPIRY_THRESHOLD_SECONDS}s"

while true; do
    check_and_refresh || true
    sleep "$CHECK_INTERVAL_SECONDS"
done
