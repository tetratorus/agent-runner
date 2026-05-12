# baw — Binance Agentic Wallet

Standalone, keyless wallet for AI agents, separated from a user's main
Binance MPC Wallet. Supports BNB Chain, Solana, Ethereum, Base.
Distributed as a Skills package — there is no standalone `baw` CLI you
can install with `npm install`.

## Prerequisites

- Node.js ≥ 18
- An active Binance account with an MPC Wallet already created in the
  Binance App. The Agentic Wallet attaches to that primary wallet.

## Install

```bash
# Non-interactive — install for a specific agent (e.g. claude-code):
npx skills add binance/binance-skills-hub/skills/binance-web3/binance-agentic-wallet \
    --agent claude-code --skill '*' --yes --global

# Or for every installed agent at once:
npx skills add binance/binance-skills-hub/skills/binance-web3/binance-agentic-wallet \
    --all --global
```

The skills CLI auto-detects which agent runtimes are present (Claude
Code, Codex, OpenCode, Aider, Cursor, OpenClaw, etc.) and registers the
skill manifest into each chosen agent's skill directory. The agent gains
new tools; there is no separate CLI binary called `baw`.

## Authenticate

Auth is driven through the agent, not via a shell command. From the
install guide:

> After installation, instruct your AI agent with: "Sign in to Binance
> Agentic Wallet"

The agent surfaces a sign-in link:

- **Mobile**: link opens the Binance app for confirmation.
- **Web**: QR code displayed; scan with the Binance app, confirm.

Sign-out: tell the agent `"Sign out"`.

## Security model

- MPC-keyless. Private key is never reconstructed on a single device.
- Security rules (daily spend limit, allowed tokens, confirmation
  requirements) are configured **only inside the Binance app**. The
  agent can read them but cannot modify them.

## Sources

- [Binance Open Platform — Agentic Wallet welcome](https://developers.binance.com/docs/agentic-wallet/welcome)
- [Install Agentic Wallet quickstart](https://developers.binance.com/docs/agentic-wallet/quickstart/install-agentic-wallet)
- [github.com/binance/binance-skills-hub](https://github.com/binance/binance-skills-hub)
- `npx skills --help`, `npx skills add --help` (probed in `node:20` container)
