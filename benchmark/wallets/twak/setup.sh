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
      rm -rf "${WORKSPACE}/.twak" "${WORKSPACE}/.env"
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
    npm install @trustwallet/cli@0.11.0
    export PATH=/workspace/node_modules/.bin:$PATH

    if twak auth status | grep -q "Status     configured"; then
      echo "twak: reusing existing credentials from /workspace/.twak/credentials.json"
    else
      if [ ! -t 0 ]; then
        echo "twak is not configured. Run this setup from a TTY or set it up manually." >&2
        exit 1
      fi
      read -r -p "TWAK access_id: " access_id
      read -r -s -p "TWAK HMAC secret: " hmac_secret
      printf "\n"
      twak init --api-key "$access_id" --api-secret "$hmac_secret"
    fi

    if twak wallet status | grep -q "Wallet     configured"; then
      echo "twak: reusing existing encrypted wallet from /workspace/.twak/wallet.json"
      if [ ! -f /workspace/.env ] || ! grep -q "^TWAK_WALLET_PASSWORD=" /workspace/.env; then
        if [ ! -t 0 ]; then
          echo "twak wallet exists, but .env lacks TWAK_WALLET_PASSWORD. Run from a TTY." >&2
          exit 1
        fi
        read -r -s -p "Existing TWAK wallet password: " wallet_password
        printf "\n"
        printf "TWAK_WALLET_PASSWORD=%s\n" "$wallet_password" > /workspace/.env
        chmod 600 /workspace/.env
      else
        echo "twak: reusing wallet password from /workspace/.env"
      fi
    else
      if [ ! -t 0 ]; then
        echo "twak wallet is not configured. Run this setup from a TTY." >&2
        exit 1
      fi
      read -r -s -p "New TWAK wallet password: " wallet_password
      printf "\n"
      twak wallet create --password "$wallet_password" --no-keychain --skip-password-check
      printf "TWAK_WALLET_PASSWORD=%s\n" "$wallet_password" > /workspace/.env
      chmod 600 /workspace/.env
    fi

    set -a
    [ -f /workspace/.env ] && source /workspace/.env
    set +a

    twak auth status
    twak wallet status
  '
