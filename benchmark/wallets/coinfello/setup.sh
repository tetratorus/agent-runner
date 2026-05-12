#!/bin/bash
# coinfello — CoinFello smart account.
# Sources:
#   - https://www.coinfello.com/
#   - https://github.com/openclaw/openclaw (CoinFello ships as an OpenClaw skill)
#
# CoinFello is not a standalone CLI like twak or awal. It exposes its wallet
# capabilities to agents via the OpenClaw skill system — installed with
# `npx skills add coinfello/...` into an agent that hosts skills (Claude
# Code, OpenClaw, Cursor). Its security model uses ERC-7710 delegations
# against an ERC-4337 smart account via the MetaMask Smart Accounts Kit.
#
# TODO: confirm the exact skill path (the published name is referenced in
# press releases but I haven't pinned the canonical npm/github source).
# For now this setup writes a placeholder so the harness can list it.
set -e

WALLET_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WS="$WALLET_DIR/workspace"
mkdir -p "$WS"
cd "$WS"

echo "[coinfello setup] skill-based install path not yet wired"
echo "[coinfello setup] see CoinFello docs / openclaw skill registry to find the actual skill name"
touch .setup-done
