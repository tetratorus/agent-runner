# baw — Binance Agentic Wallet

Standalone, keyless wallet for AI agents, separated from a user's main
Binance MPC Wallet. Supports BNB Chain, Solana, Ethereum, Base.
The benchmark installs both the `baw` CLI and the Binance Agentic Wallet
skill so agents can either follow the local skill docs or shell out to
`baw` directly.

## Prerequisites

- Node.js ≥ 18
- An active Binance account with an MPC Wallet already created in the
  Binance App. The Agentic Wallet attaches to that primary wallet.

## Install

```bash
./setup.sh
```

The setup script installs `@binance/agentic-wallet@1.0.9` into
`workspace/node_modules`, installs the `binance-agentic-wallet` skill into
`workspace/.agents`, and writes `workspace/.env` with:

- `BINANCE_INSTANCE_ID=baw-benchmark-v1`
- `BINANCE_BAW_DIR=/workspace/.baw`

`BINANCE_INSTANCE_ID` must be stable because the CLI encrypts
`.baw/session.json` using this value when it is set. Without it, Docker
container identity changes can make a prepared session unreadable during
benchmark runs.

Useful setup flags:

```bash
./setup.sh --clean        # reinstall node dependencies
./setup.sh --reset-state  # discard BAW auth/session state and re-auth
```

## Authenticate

Auth uses the CLI QR flow:

```bash
baw auth signin --json
baw auth verify --qrCodeId <id> --json
baw wallet status --json
```

`./setup.sh` runs this flow interactively. Scan or open the returned Binance
link, approve in the Binance app, then press Enter so setup can verify and
persist the session under `workspace/.baw`.

Sign-out:

```bash
baw auth signout --json
```

## Security model

- MPC-keyless. Private key is never reconstructed on a single device.
- Security rules (daily spend limit, allowed tokens, confirmation
  requirements) are configured **only inside the Binance app**. The
  agent can read them but cannot modify them.

## Sources

- [Binance Open Platform — Agentic Wallet welcome](https://developers.binance.com/docs/agentic-wallet/welcome)
- [Install Agentic Wallet quickstart](https://developers.binance.com/docs/agentic-wallet/quickstart/install-agentic-wallet)
- [github.com/binance/binance-skills-hub](https://github.com/binance/binance-skills-hub)
- `baw --help`, `baw auth --help`, `npx skills add --help` (probed in `node:20` container)
