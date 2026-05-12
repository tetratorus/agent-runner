FROM agent-runner/base:latest

USER root

# Install Goose CLI (precompiled binary from GitHub releases).
# CONFIGURE=false skips the interactive provider setup that would otherwise
# fail in a non-tty Docker build. Copy the binary to /usr/local/bin so both
# root and the agent user can run it.
RUN curl -fsSL https://github.com/block/goose/releases/download/stable/download_cli.sh | CONFIGURE=false bash \
    && cp /root/.local/bin/goose /usr/local/bin/goose \
    && chmod +x /usr/local/bin/goose

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
# Goose non-interactive
goose run -t "$PROMPT" 2>&1 || true
echo ""
echo "=== Done ==="
SCRIPT
RUN chmod +x /usr/local/bin/run-agent

USER agent
WORKDIR /workspace
ENTRYPOINT ["/usr/local/bin/run-agent"]
