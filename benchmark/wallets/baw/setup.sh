#!/bin/bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="${DIR}/workspace"
IMAGE="${WALLET_SETUP_IMAGE:-node:20}"
PLATFORM="${WALLET_SETUP_PLATFORM:-linux/amd64}"
ENV_FILE="${WORKSPACE}/.env"

mkdir -p "${WORKSPACE}"

for arg in "$@"; do
  case "${arg}" in
    --clean|--clean-deps)
      rm -rf "${WORKSPACE}/node_modules" "${WORKSPACE}/package-lock.json"
      ;;
    --reset-state)
      rm -rf "${WORKSPACE}/.baw" "${ENV_FILE}"
      ;;
    *)
      echo "Usage: $0 [--clean|--clean-deps] [--reset-state]" >&2
      exit 2
      ;;
  esac
done

touch "${ENV_FILE}"
if ! grep -q "^BINANCE_INSTANCE_ID=" "${ENV_FILE}"; then
  printf "BINANCE_INSTANCE_ID=%s\n" "${BINANCE_INSTANCE_ID:-baw-benchmark-v1}" >> "${ENV_FILE}"
fi
if ! grep -q "^BINANCE_BAW_DIR=" "${ENV_FILE}"; then
  printf "BINANCE_BAW_DIR=/workspace/.baw\n" >> "${ENV_FILE}"
fi
chmod 600 "${ENV_FILE}"

DOCKER_RUN_ARGS=(--rm -i)
if [ -t 0 ]; then
  DOCKER_RUN_ARGS=(--rm -it)
fi

docker run "${DOCKER_RUN_ARGS[@]}" \
  --platform "${PLATFORM}" \
  -v "${WORKSPACE}:/workspace:rw" \
  -w /workspace \
  -e HOME=/workspace \
  --env-file "${ENV_FILE}" \
  "${IMAGE}" \
  bash -lc '
    set -euo pipefail
    npm install @binance/agentic-wallet@1.0.9
    export PATH=/workspace/node_modules/.bin:$PATH

    npx --yes skills add binance/binance-skills-hub/skills/binance-web3/binance-agentic-wallet \
      --agent codex --skill "*" --yes --global --copy

    status_json="$(baw wallet status --json || true)"
    printf "%s\n" "$status_json"
    if printf "%s\n" "$status_json" | grep -q "\"status\": \"CONNECTED\""; then
      echo "baw: reusing existing session from /workspace/.baw/session.json"
      exit 0
    fi

    if [ ! -t 0 ]; then
      echo "baw is not connected. Run this setup from a TTY to scan/approve the Binance QR flow." >&2
      exit 1
    fi

    signin_json="$(baw auth signin --json)"
    printf "%s\n" "$signin_json"
    qr_code_id="$(printf "%s\n" "$signin_json" | node -e "let s=\"\";process.stdin.on(\"data\",d=>s+=d);process.stdin.on(\"end\",()=>{const j=JSON.parse(s); console.log(j.data && j.data.qrCodeId || \"\")})")"

    if [ -z "$qr_code_id" ]; then
      echo "Could not read qrCodeId from baw auth signin output." >&2
      exit 1
    fi

    read -r -p "Scan/approve in Binance, then press Enter to verify..."
    baw auth verify --qrCodeId "$qr_code_id" --json
    final_status="$(baw wallet status --json)"
    printf "%s\n" "$final_status"
    if ! printf "%s\n" "$final_status" | grep -q "\"status\": \"CONNECTED\""; then
      echo "baw auth did not finish with CONNECTED status." >&2
      exit 1
    fi
  '
