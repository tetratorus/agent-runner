#!/bin/bash
# Runtime adapter for prepared benchmark wallet workspaces.
#
# The agent CLIs need their normal HOME (for Codex/Claude/Goose config), while
# wallet CLIs expect auth/session/config under HOME. Link selected wallet state
# directories from the copied /workspace into HOME and put local npm bins first.

set -euo pipefail

export PATH="/workspace/node_modules/.bin:${PATH}"
export ELECTRON_DISABLE_SANDBOX="${ELECTRON_DISABLE_SANDBOX:-1}"

rm -rf /tmp/payments-mcp-ui-bridge /tmp/payments-mcp-ui.lock
find /workspace/.config/Electron -name LOCK -type f -delete 2>/dev/null || true

if [ -z "${DISPLAY:-}" ] && command -v Xvfb >/dev/null 2>&1; then
  export DISPLAY=:99
  rm -f "/tmp/.X${DISPLAY#:}-lock" "/tmp/.X11-unix/X${DISPLAY#:}" 2>/dev/null || true
  Xvfb "${DISPLAY}" -screen 0 1280x720x24 >/tmp/wallet-xvfb.log 2>&1 &
fi

link_wallet_path() {
  local name="$1"
  local src="/workspace/${name}"
  local dst="${HOME}/${name}"

  if [ ! -e "${src}" ]; then
    return 0
  fi
  if [ -e "${dst}" ] || [ -L "${dst}" ]; then
    return 0
  fi

  mkdir -p "$(dirname "${dst}")"
  ln -s "${src}" "${dst}"
}

for path in \
  .agents \
  .awal \
  .baw \
  .cache \
  .clawdbot \
  .coinfello \
  .local \
  .phantom-mcp \
  .twak
do
  link_wallet_path "${path}"
done
