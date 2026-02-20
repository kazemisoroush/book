#!/bin/bash
# Pre-execution hook to check AWS credentials before Claude Code commands
# This ensures credentials are always valid when needed

# Only run for Claude Code, not for every bash command
if [ -n "$CLAUDE_CODE_SESSION" ] || [ -n "$ANTHROPIC_API_KEY" ]; then
    # Silent check - only output on failure
    if ! aws sts get-caller-identity --profile "${AWS_PROFILE:-bedrock}" &>/dev/null 2>&1; then
        echo "⚠️  AWS credentials expired. Attempting refresh..."
        /workspaces/apply/.devcontainer/refresh-aws-credentials.sh || true
    fi
fi
