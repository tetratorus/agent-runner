FROM agent-runner/base:latest

USER root

# Install Goose CLI (precompiled binary from GitHub releases)
RUN curl -fsSL https://github.com/block/goose/releases/download/stable/download_cli.sh | bash

# Goose installs to ~/.local/bin
ENV PATH="/root/.local/bin:${PATH}"

# Create entrypoint script
RUN cat > /usr/local/bin/run-agent << 'SCRIPT'
#!/bin/bash
set -e
PROMPT=$(cat "$PROMPT_FILE")
echo "=== Goose (Block) ==="
echo "Prompt: $PROMPT"
echo "Workspace: $WORKSPACE"
echo ""
# Configure provider non-interactively
export GOOSE_PROVIDER="${GOOSE_PROVIDER:-anthropic}"
export GOOSE_MODEL="${GOOSE_MODEL:-claude-sonnet-4-20250514}"
cd "$WORKSPACE"
# Goose non-interactive: pipe prompt and exit
echo "$PROMPT" | goose run --stdin 2>&1 || true
echo ""
echo "=== Done ==="
SCRIPT
RUN chmod +x /usr/local/bin/run-agent

USER agent
WORKDIR /workspace
ENV PATH="/home/agent/.local/bin:${PATH}"
ENTRYPOINT ["/usr/local/bin/run-agent"]
