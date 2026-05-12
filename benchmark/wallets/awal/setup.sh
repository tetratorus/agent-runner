#!/bin/bash
# awal — Coinbase Agentic Wallet CLI.
# Sources:
#   - npm:  https://www.npmjs.com/package/awal
#   - docs: https://docs.cdp.coinbase.com/agentic-wallet/cli/quickstart
#
# Auth flow is email-OTP — you have to complete it interactively at least
# once on this machine before the benchmark can run (npx awal will store
# session state per-user). After auth, the cloned workspace inherits that
# state via $HOME/.awal/ or similar; for a fully containerised setup you
# may need to bake session files into the workspace.
set -e

WALLET_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WS="$WALLET_DIR/workspace"
mkdir -p "$WS"
cd "$WS"

if [ ! -d node_modules/awal ]; then
  echo "[awal setup] installing awal into $WS"
  [ -f package.json ] || npm init -y >/dev/null
  npm install --silent awal
else
  echo "[awal setup] awal already installed"
fi

if [ ! -f .env ]; then
  cat > .env <<'ENV'
# Fill in after `npx awal auth login <email>` + `npx awal auth verify`.
# awal stores session state in $HOME/.awal/ — make sure that directory is
# accessible to the agent container if you mount it from the host.
AWAL_EMAIL=
ENV
  echo "[awal setup] wrote .env stub — run \`npx awal auth login <email>\` interactively before benchmarking"
fi

touch .setup-done
echo "[awal setup] done"
