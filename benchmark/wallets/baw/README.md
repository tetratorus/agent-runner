# baw — Binance Agentic Wallet

Standalone, keyless wallet for AI agents, separated from a user's main
Binance MPC Wallet. Supports BNB Chain, Solana, Ethereum, Base.
Distributed as a Skills package — not a standalone `npm install` CLI.

## Prerequisites

- Node.js ≥ 18
- An active Binance account with an MPC Wallet already created in the
  Binance App. The Agentic Wallet attaches to that primary wallet.

## Install

```bash
npx skills add binance/binance-skills-hub/skills/binance-web3/binance-agentic-wallet
```

Quote from the install guide:

> The CLI will be set up automatically.

So `baw` becomes available as part of the skills package; you don't
`npm install baw` separately.

## Authenticate

Drive the auth via the AI agent itself:

> After installation, instruct your AI agent with: "Sign in to Binance
> Agentic Wallet"

The agent then surfaces a sign-in link. Two paths:

- **Mobile**: link redirects to the Binance app.
- **Web**: scan the displayed QR code in the Binance app, confirm.

Sign-out is `"Sign out"` to the agent.

Security rules (daily limits, allowed tokens) are configurable **only
inside the Binance app** — the AI can read them but not modify them.

## Env vars / persistence

Not documented. The MPC architecture means the private key is never
fully reconstructed on any device; session state location isn't
specified in the public docs.

## Sources

- [Binance Open Platform — Agentic Wallet welcome](https://developers.binance.com/docs/agentic-wallet/welcome)
- [Install Agentic Wallet quickstart](https://developers.binance.com/docs/agentic-wallet/quickstart/install-agentic-wallet)
- [github.com/binance/binance-skills-hub](https://github.com/binance/binance-skills-hub)
