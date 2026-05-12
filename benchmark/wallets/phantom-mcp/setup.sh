#!/bin/bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="${DIR}/workspace"
IMAGE="${WALLET_SETUP_IMAGE:-node:20}"
PLATFORM="${WALLET_SETUP_PLATFORM:-linux/amd64}"

mkdir -p "${WORKSPACE}"

for arg in "$@"; do
  case "${arg}" in
    --clean|--clean-deps)
      rm -rf "${WORKSPACE}/node_modules" "${WORKSPACE}/package-lock.json"
      ;;
    --reset-state)
      rm -rf "${WORKSPACE}/.phantom-mcp"
      ;;
    *)
      echo "Usage: $0 [--clean|--clean-deps] [--reset-state]" >&2
      exit 2
      ;;
  esac
done

docker run --rm -it \
  --platform "${PLATFORM}" \
  -v "${WORKSPACE}:/workspace:rw" \
  -w /workspace \
  -e HOME=/workspace \
  "${IMAGE}" \
  bash -lc '
    set -euo pipefail
    npm install @phantom/mcp-server@1.2.7
    export PATH=/workspace/node_modules/.bin:$PATH

    cat > /workspace/.mcp.json <<'"'"'JSON'"'"'
{
  "mcpServers": {
    "phantom": {
      "type": "stdio",
      "command": "/workspace/node_modules/.bin/phantom",
      "args": [
        "--mcp"
      ],
      "env": {}
    }
  }
}
JSON

    # `phantom wallet status` currently initializes auth when no session exists,
    # so use the session file as the non-interactive readiness gate.
    if [ -s /workspace/.phantom-mcp/session.json ]; then
      echo "phantom-mcp: reusing existing session from /workspace/.phantom-mcp/session.json"
      phantom wallet status --format json
      exit 0
    fi

    if [ ! -t 0 ]; then
      echo "Phantom is not authenticated. Run setup from a TTY for device-code auth." >&2
      exit 1
    fi

    phantom login --display-mode text
    phantom wallet status --format json
  '
