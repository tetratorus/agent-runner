#!/bin/bash
# twak — Trust Wallet Agent Kit CLI.
# Sources:
#   - npm:    https://www.npmjs.com/package/@trustwallet/cli
#   - docs:   https://developer.trustwallet.com/developer/agent-sdk
#   - portal: https://portal.trustwallet.com  (developer key / wallet provisioning)
#   - blog:   https://trustwallet.com/blog/announcements/introducing-the-trust-wallet-agent-kit-twak-your-ai-agent-can-now-act-on-crypto
#
# Result: wallets/twak/workspace/ contains the installed twak CLI + a .env
# with the test wallet's credentials. run.py clones this directory into
# each cell so every test starts from the same prepared state.
set -e

# This script's directory is wallets/twak/. Workspace template lives next door.
WALLET_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WS="$WALLET_DIR/workspace"
mkdir -p "$WS"
cd "$WS"

# --- Install the twak CLI locally (so it travels with the cloned workspace).
if [ ! -d node_modules/@trustwallet/cli ]; then
  echo "[twak setup] installing @trustwallet/cli into $WS"
  [ -f package.json ] || npm init -y >/dev/null
  npm install --silent @trustwallet/cli
else
  echo "[twak setup] @trustwallet/cli already installed"
fi

# --- Wire up PATH so `twak` resolves inside the container.
cat > .envrc <<'ENVRC'
# Sourced by tools that respect .envrc; harmless if nothing reads it.
export PATH="$PWD/node_modules/.bin:$PATH"
ENVRC

# --- Test wallet credentials.
# Fill these in manually (or via a separate provisioning script). Without
# real values, every execute_required test on twak will fail — which is
# fine for dry-runs of the harness itself but not for real evaluation.
if [ ! -f .env ]; then
  cat > .env <<'ENV'
# Replace these with a funded Base Sepolia test wallet.
WALLET_PRIVATE_KEY=
BASE_RPC_URL=https://sepolia.base.org
# Optional: a Basescan API key for tx confirmation in the agent's tooling.
BASESCAN_API_KEY=
ENV
  echo "[twak setup] wrote .env stub — fill in WALLET_PRIVATE_KEY before running execute_required tests"
fi

touch .setup-done
echo "[twak setup] done"
