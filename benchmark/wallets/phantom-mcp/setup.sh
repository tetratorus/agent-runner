#!/bin/bash
# phantom-mcp — Phantom MCP server (Phase 2).
# Sources:
#   - npm:  https://www.npmjs.com/package/@phantom/mcp-server
#   - docs: https://docs.phantom.com/resources/mcp-server
#   - help: https://help.phantom.com/hc/en-us/articles/49235725504147-Get-started-with-Phantom-MCP
#
# phantom-mcp is an MCP server, not a CLI. Agents that speak MCP connect
# to it and call its tools (sign_message, send_transaction, swap, ...).
# Authentication is a browser-based OAuth flow (Google/Apple) at
# connect.phantom.app; the session is stored in ~/.phantom-mcp/session.json
# with 0600 perms.
#
# TODO (Phase 2): for each MCP-capable agent (currently just claude-code),
# wire the agent's container to launch the phantom-mcp server and point
# its MCP config at it. The shared $HOME/.phantom-mcp/session.json from
# the host needs to be made readable inside the container too.
set -e

WALLET_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WS="$WALLET_DIR/workspace"
mkdir -p "$WS"
cd "$WS"

if [ ! -d node_modules/@phantom/mcp-server ]; then
  echo "[phantom-mcp setup] installing @phantom/mcp-server into $WS"
  [ -f package.json ] || npm init -y >/dev/null
  npm install --silent @phantom/mcp-server
else
  echo "[phantom-mcp setup] @phantom/mcp-server already installed"
fi

echo "[phantom-mcp setup] complete the OAuth flow manually:"
echo "    npx @phantom/mcp-server login"
echo "  session lands in ~/.phantom-mcp/session.json"
touch .setup-done
