#!/bin/bash
# baw — Binance Agentic Wallet (Phase 2).
# Sources:
#   - docs:    https://developers.binance.com/docs/agentic-wallet/welcome
#   - skills:  https://github.com/binance/binance-skills-hub
#
# baw is distributed as a skill, not a standalone CLI. The install command
# in the docs is:
#   npx skills add binance/binance-skills-hub/skills/binance-web3/binance-agentic-wallet
# That only does anything inside an agent that supports the "skills"
# protocol (Claude Code, Cursor, OpenClaw). For agents in our matrix
# that don't, baw is unreachable — they should be skipped in run.py
# similarly to how phantom-mcp is skipped for non-MCP agents.
#
# TODO (Phase 2): wire a per-agent install step that runs
# `npx skills add …` inside the agent's container before the cell.
set -e

WALLET_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WS="$WALLET_DIR/workspace"
mkdir -p "$WS"
cd "$WS"

echo "[baw setup] skill-based install — not yet wired into per-agent containers"
echo "[baw setup] install command: npx skills add binance/binance-skills-hub/skills/binance-web3/binance-agentic-wallet"
touch .setup-done
