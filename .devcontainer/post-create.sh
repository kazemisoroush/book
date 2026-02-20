#!/bin/bash
set -e

echo "Installing Terraform..."
if ! command -v terraform &> /dev/null; then
    # Remove problematic Yarn repository if it exists
    sudo rm -f /etc/apt/sources.list.d/yarn.list

    wget -O- https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor --yes -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
    echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list
    sudo apt update
    sudo apt install -y terraform
    echo "Terraform installed successfully!"
else
    echo "Terraform already installed."
fi

echo "Configuring Git..."
git config --global user.email 'kazemi.soroush@gmail.com'
git config --global user.name 'Soroush Kazemi'

echo "Configuring Claude Code for AWS Bedrock..."
CLAUDE_HOME="${HOME}"
mkdir -p "${CLAUDE_HOME}/.claude"

# Claude Code will automatically use AWS Bedrock when AWS credentials are available
cat > "${CLAUDE_HOME}/.claude/settings.json" <<'JSON'
{
  "$schema": "https://json.schemastore.org/claude-code-settings.json"
}
JSON

echo "Claude Code ready for AWS Bedrock"

echo "Restoring and building .NET project..."
dotnet restore
dotnet tool restore
dotnet format
dotnet build
dotnet test

echo "Starting AWS credential watchdog..."
# Kill any existing watchdog processes
pkill -f "credential-watchdog.sh" 2>/dev/null || true

# Start watchdog in background with output to log file
nohup /workspaces/apply/.devcontainer/credential-watchdog.sh > /tmp/aws-credential-watchdog.log 2>&1 &
WATCHDOG_PID=$!
echo "AWS credential watchdog started (PID: $WATCHDOG_PID)"
echo "To view logs: tail -f /tmp/aws-credential-watchdog.log"

echo "Post-create setup complete!"