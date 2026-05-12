#!/bin/bash
# Set up the coinfello wallet workspace for the benchmark.
#
# coinfello stores everything we need (private key, smart account address,
# session token, chat id) in workspace/.clawdbot/skills/coinfello/config.json.
# That file is portable: once it has `session_token`, fresh test containers
# can use `send_prompt` etc. without any further auth.
#
# The only step that needs network plumbing is `sign_in` — it asks the
# MetaMask Smart-Accounts library to inspect the account on Ethereum mainnet,
# which requires a working RPC. Public viem defaults rate-limit / hang in
# practice, so we pass an explicit RPC. Resolution order:
#
#   1. RPC_URL_OVERRIDE (any env var)             — used as-is
#   2. INFURA_API_KEY                             — Infura mainnet
#   3. https://ethereum.publicnode.com            — free public fallback
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="${DIR}/workspace"
IMAGE="${WALLET_SETUP_IMAGE:-node:20}"
PLATFORM="${WALLET_SETUP_PLATFORM:-linux/amd64}"
CONFIG_FILE="${WORKSPACE}/.clawdbot/skills/coinfello/config.json"

mkdir -p "${WORKSPACE}"

for arg in "$@"; do
  case "${arg}" in
    --clean|--clean-deps)
      rm -rf "${WORKSPACE}/node_modules" "${WORKSPACE}/package-lock.json"
      ;;
    --reset-state)
      rm -rf "${WORKSPACE}/.clawdbot"
      ;;
    *)
      echo "Usage: $0 [--clean|--clean-deps] [--reset-state]" >&2
      exit 2
      ;;
  esac
done

if [ -n "${RPC_URL_OVERRIDE:-}" ]; then
  RPC_URL="${RPC_URL_OVERRIDE}"
elif [ -n "${INFURA_API_KEY:-}" ]; then
  RPC_URL="https://mainnet.infura.io/v3/${INFURA_API_KEY}"
else
  RPC_URL="https://ethereum.publicnode.com"
  echo "coinfello-setup: no RPC_URL_OVERRIDE or INFURA_API_KEY — falling back to ${RPC_URL} (may rate-limit)" >&2
fi

docker run --rm -it \
  --platform "${PLATFORM}" \
  -v "${WORKSPACE}:/workspace:rw" \
  -w /workspace \
  -e HOME=/workspace \
  -e RPC_URL_OVERRIDE="${RPC_URL}" \
  "${IMAGE}" \
  bash -lc '
    set -euo pipefail
    npm install @coinfello/agent-cli@0.3.6
    export PATH=/workspace/node_modules/.bin:$PATH

    if ! coinfello get_account >/dev/null 2>&1; then
      echo "coinfello: creating smart account"
      coinfello create_account
    fi
    echo "coinfello: account = $(coinfello get_account | head -1)"

    config=/workspace/.clawdbot/skills/coinfello/config.json
    if [ -f "$config" ] && grep -q "\"session_token\"" "$config"; then
      echo "coinfello: existing session_token found — skipping sign_in"
    else
      echo "coinfello: signing in (RPC=$RPC_URL_OVERRIDE)"
      coinfello sign_in
    fi

    # Sanity check: a one-word prompt confirms the session is live.
    coinfello send_prompt "respond with the single word ok" 2>&1 | tail -3 || true
  '

echo
echo "Workspace ready: ${WORKSPACE}"
echo "Config: ${CONFIG_FILE}"
