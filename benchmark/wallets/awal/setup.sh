#!/bin/bash
# Set up the awal wallet workspace for the benchmark.
#
# Strategy: the in-container `awal` is a thin shim that forwards argv to the
# host's authenticated awal CLI via TCP (see awal-shim and host-awal-proxy.py).
# We don't install or run the real awal inside the container — that path
# couldn't persist auth across container exits and was the source of much pain.
#
# Requirement: `awal` installed and authenticated on the host (`awal status`
# shows `authenticated: true`). The host proxy is started automatically by
# `benchmark/run.py`; no separate process to babysit.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="${DIR}/workspace"
SHIM="${DIR}/awal-shim"

if [ ! -x "${SHIM}" ]; then
  chmod +x "${SHIM}" 2>/dev/null || {
    echo "setup: ${SHIM} missing or not executable" >&2
    exit 1
  }
fi

if ! command -v awal >/dev/null 2>&1; then
  echo "setup: \`awal\` not found on host PATH. Install it first (npm i -g awal)." >&2
  exit 1
fi

echo "setup: checking host awal auth..."
awal status --json | python3 -c '
import json, sys
data = json.load(sys.stdin)
auth = data.get("auth") or {}
if not auth.get("authenticated"):
    print("setup: host awal is NOT authenticated. Run `awal auth login <email>` then re-run setup.", file=sys.stderr)
    sys.exit(1)
email = auth.get("email", "?")
print("setup: host awal authenticated as " + email + " OK")
'

mkdir -p "${WORKSPACE}/node_modules/.bin"
cat > "${WORKSPACE}/package.json" <<'JSON'
{"name":"awal-bench","version":"1.0.0","private":true}
JSON

install -m 0755 "${SHIM}" "${WORKSPACE}/node_modules/.bin/awal"
echo "setup: installed shim at ${WORKSPACE}/node_modules/.bin/awal"

echo
echo "Workspace ready: ${WORKSPACE}"
echo "Run benchmark/run.py as usual; it will spawn the host proxy itself."
